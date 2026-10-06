"""Sprites, rasterised by hand.

MLX has no shapes and no images (``notes.txt``), so every sprite here is
computed from geometry and stamped with ``Surface.fill`` -- the one drawing
call the platform does provide.  The player is computed because it has to
move (a chomping mouth); the ghost is the arcade bitmap, scaled to whatever
radius the caller asks for, because the real sprite is a fixed pixel-art
shape and no formula reproduces it faithfully.

MLX also has no alpha channel, so soft edges are faked the cheap way: the
silhouette is stamped once slightly oversized in a dark shade of its own
colour, then again at true size on top.

Everything here draws in *pixel* coordinates with the sprite centred on
``(cx, cy)``, so callers only have to convert a world position once.
"""

import enum
import math

import pygame

from pacman.core.entities import Mover

# An RGB colour and a 2-D vector, written out often enough to name.
Color = tuple[int, int, int]
Vec = tuple[float, float]

# A rim dark enough to read as an outline against the maze, a highlight
# bright enough to make the top of a shape look lit from above.
RIM = 0.45
LIT = 1.18


def shade(color: Color, factor: float) -> Color:
    """Return *color* scaled by *factor* and clamped to opaque RGB."""
    r, g, b = (max(0, min(255, round(c * factor))) for c in color)
    return (r, g, b)


def disc(screen: pygame.Surface, cx: int, cy: int, radius: float,
         color: Color, rim: bool = True) -> None:
    """Stamp a filled circle, one scanline at a time.

    Args:
        cx, cy: centre in pixels.
        radius: radius in pixels.
        color: body colour.
        rim: stamp a darker outline just outside the circle.
    """
    r = int(math.ceil(radius))
    body = shade(color, LIT)
    edge = shade(color, RIM)
    for dy in range(-r, r + 1):
        span = math.sqrt(max(0.0, radius * radius - dy * dy))
        left = int(round(cx - span))
        right = int(round(cx + span))
        if right < left:
            continue
        if rim:
            screen.fill(edge, (left - 1, cy + dy, right - left + 3, 1))
        fill = body if rim else color
        screen.fill(fill, (left, cy + dy, right - left + 1, 1))


def _wedge(facing: Vec, half_angle: float) -> tuple[Vec, Vec]:
    """Unit vectors along both edges of a wedge about *facing*."""
    fx, fy = facing
    c, s = math.cos(half_angle), math.sin(half_angle)
    return ((fx * c - fy * s, fx * s + fy * c),
            (fx * c + fy * s, -fx * s + fy * c))


def pacman(screen: pygame.Surface, cx: int, cy: int, radius: float,
           color: Color, facing: Vec = (1, 0), mouth: float = 0.0) -> None:
    """Stamp the player: a flat disc with a wedge bitten out of the front.

    Args:
        cx, cy: centre in pixels.
        radius: body radius in pixels.
        color: body colour.
        facing: unit vector the mouth points along.
        mouth: 0 for a nearly closed mouth, 1 for wide open, up to 2 for
            the death animation where the whole disc is bitten away.
    """
    mouth = max(0.0, min(2.0, mouth))
    # 0..1 is the chomp (9 to 29 degrees); 1..2 keeps opening until the
    # wedge swallows the disc, which is the death animation.
    half = math.radians(9.0 + 20.0 * mouth if mouth <= 1.0
                        else 29.0 + 151.0 * (mouth - 1.0))
    bite = _wedge(facing, half)
    r = int(math.ceil(radius))
    for dy in range(-r, r + 1):
        span = math.sqrt(max(0.0, radius * radius - dy * dy))
        x0 = int(round(-span))
        x1 = int(round(span))
        run_start = None
        for dx in range(x0, x1 + 1):
            inside = (dx * bite[0][1] - dy * bite[0][0] >= 0
                      and bite[1][0] * dy - bite[1][1] * dx >= 0)
            if inside and run_start is not None:
                screen.fill(color, (cx + run_start, cy + dy,
                                    dx - run_start, 1))
                run_start = None
            elif not inside and run_start is None:
                run_start = dx
        if run_start is not None:
            screen.fill(color, (cx + run_start, cy + dy,
                                x1 - run_start + 1, 1))


# --- The ghost ------------------------------------------------------------
#
# A round head on a straight body whose hem is cut into three triangular
# notches.  The notches shift half a step between the two animation
# frames, which is what makes the skirt wave.
_PUPIL = (30, 30, 120)
_WHITE = (255, 255, 255)


def _sign(value: float) -> int:
    """-1, 0 or 1, with a dead zone so a near-zero heading counts as still."""
    return (value > 0.3) - (value < -0.3)


def _skirt_row(screen: pygame.Surface, left: int, right: int, y: int,
               notches: list[tuple[int, int]], color: Color) -> None:
    """Fill one body row from *left* to *right* minus the *notches*.

    Each notch is a ``(start, end)`` pixel interval left empty.
    """
    x = left
    for start, end in sorted(notches):
        start, end = max(start, left), min(end, right)
        if end <= start:
            continue
        if start > x:
            screen.fill(color, (x, y, start - x, 1))
        x = max(x, end)
    if right > x:
        screen.fill(color, (x, y, right - x, 1))


def ghost(screen: pygame.Surface, cx: int, cy: int, radius: float,
          color: Color, facing: Vec = (0, -1), phase: int = 0,
          scared: bool = False, face: Color = (255, 255, 255),
          pixel: int = 0, eyes_only: bool = False) -> None:
    """Stamp the ghost, centred on ``(cx, cy)``, inside a ``2r`` square.

    Args:
        cx, cy: centre in pixels.
        radius: half the sprite's side in pixels.
        color: body colour.
        facing: heading; the pupils lean that way.
        phase: 0/1, which way the skirt waves this frame.
        scared: draw the frightened face instead of the hunting eyes.
        face: colour of the frightened eyes and mouth.
        pixel: ignored; kept so older call sites keep working.
        eyes_only: draw just the eyes, which is what an eaten ghost looks
            like on its way home.
    """
    r = max(2, int(round(radius)))
    left, right = cx - r, cx + r
    if not eyes_only:
        # Head: the upper half disc.
        for dy in range(-r, 1):
            span = int(round(math.sqrt(max(0.0, r * r - dy * dy))))
            screen.fill(color, (cx - span, cy + dy, 2 * span + 1, 1))
        # Body with a notched hem.
        wave = max(2, r // 3)
        step = (2.0 * r) / 3.0
        if int(phase) % 2 == 0:
            centres = [left + (k + 0.5) * step for k in range(3)]
        else:
            centres = [left + k * step for k in range(4)]
        for row in range(1, r + 1):
            y = cy + row
            depth = row - (r - wave)
            notches = []
            if depth > 0:
                half = depth / wave * step / 2.0
                notches = [(int(round(c - half)), int(round(c + half)))
                           for c in centres]
            _skirt_row(screen, left, right + 1, y, notches, color)

    if scared and not eyes_only:
        eye = max(1, r // 5)
        for side in (-1, 1):
            screen.fill(face, (cx + side * r * 2 // 5 - eye // 2,
                               cy - r // 3, eye + 1, eye + 1))
        zig = max(1, r // 6)
        for i in range(-3, 4):
            screen.fill(face, (cx + i * zig - zig // 2,
                               cy + r // 5 + (zig if i % 2 else 0),
                               zig, zig))
        return

    eye_r = max(2, int(r * 0.28))
    pupil = max(1, int(r * 0.14))
    dx, dy = _sign(facing[0]), _sign(facing[1])
    for side in (-1, 1):
        ex = cx + int(round(side * r * 0.38))
        ey = cy - int(round(r * 0.25))
        disc(screen, ex, ey, eye_r, _WHITE, rim=False)
        disc(screen, ex + dx * pupil, ey + dy * pupil, pupil, _PUPIL,
             rim=False)


def facing_of(entity: Mover) -> Vec:
    """Unit vector for an entity's heading, defaulting to *up* when still."""
    if entity.direction is None:
        return (0.0, -1.0)
    return (float(entity.direction.dx), float(entity.direction.dy))


class CreatureType(enum.Enum):
    """Marks what a maze cell is. Kept for the wall/empty bookkeeping."""
    WALL = "wall"
    EMPTY = "empty"
