"""Sprites, rasterised by hand.

MLX has no shapes and no images (``notes.txt``), so every sprite here is
computed from geometry and stamped with ``Surface.fill`` -- the one drawing
call the platform does provide.  The shapes are *computed* rather than kept
as pixel-art tables because they have to move: a chomping mouth and a ghost
whose eyes follow its heading are just different numbers, and a table would
need a hand-drawn copy per frame per direction.

MLX also has no alpha channel, so soft edges are faked the cheap way: the
silhouette is stamped once slightly oversized in a dark shade of its own
colour, then again at true size on top.  That single rim reads as both an
outline and a hint of antialiasing, and costs one extra fill per scanline.

Everything here draws in *pixel* coordinates with the sprite centred on
``(cx, cy)``, so callers only have to convert a world position once.
"""

import enum
import math

import pygame

from pacman.core.entities import Mover

# A rim dark enough to read as an outline against the maze, a highlight
# bright enough to make the top of a shape look lit from above.
RIM = 0.45
LIT = 1.18


def shade(color: tuple, factor: float) -> tuple:
    """Return *color* scaled by *factor* and clamped to opaque RGB."""
    return tuple(max(0, min(255, round(c * factor))) for c in color)


def disc(screen: pygame.Surface, cx: int, cy: int, radius: float, color: tuple,
         rim: bool = True) -> None:
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


def _wedge(facing: tuple, half_angle: float) -> tuple:
    """Unit vectors along both edges of a wedge about *facing*."""
    fx, fy = facing
    c, s = math.cos(half_angle), math.sin(half_angle)
    return ((fx * c - fy * s, fx * s + fy * c),
            (fx * c + fy * s, -fx * s + fy * c))


def pacman(screen: pygame.Surface, cx: int, cy: int, radius: float,
           color: tuple, facing: tuple = (1, 0), mouth: float = 0.0) -> None:
    """Stamp the player: a disc with a wedge bitten out of the front.

    Args:
        cx, cy: centre in pixels.
        radius: body radius in pixels.
        color: body colour.
        facing: unit vector the mouth points along.
        mouth: 0 for a closed mouth, 1 for wide open.
    """
    half = math.radians(9.0 + 33.0 * max(0.0, min(1.0, mouth)))
    # Two nested wedges: the narrow one is removed, the wide one is dimmed.
    # That gives the mouth a shaded lip instead of a hard black cut.
    bite = _wedge(facing, half)
    lip = _wedge(facing, half * 1.55)
    body, edge = shade(color, LIT), shade(color, RIM)
    dim = shade(color, 0.5)
    limit = (radius + 1) * (radius + 1)
    r = int(math.ceil(radius)) + 1
    for dy in range(-r, r + 1):
        y = cy + dy
        for dx in range(-r, r + 1):
            d2 = dx * dx + dy * dy
            if d2 > radius * radius:
                if d2 > limit:
                    continue
                screen.fill(edge, (cx + dx, y, 1, 1))
                continue
            x = cx + dx
            if (dx * bite[0][1] - dy * bite[0][0] >= 0
                    and bite[1][0] * dy - bite[1][1] * dx >= 0):
                continue
            if (dx * lip[0][1] - dy * lip[0][0] >= 0
                    and lip[1][0] * dy - lip[1][1] * dx >= 0):
                screen.fill(dim, (x, y, 1, 1))
            else:
                screen.fill(body, (x, y, 1, 1))


def ghost(screen: pygame.Surface, cx: int, cy: int, radius: float,
          color: tuple, facing: tuple = (0, -1), phase: int = 0,
          scared: bool = False, face: tuple = (255, 255, 255)) -> None:
    """Stamp a ghost: domed head, straight flanks, scalloped skirt, eyes.

    Drawn a column at a time rather than a scanline at a time.  The dome
    wants scanlines, but the skirt wants vertical notches bitten up into
    the bottom edge, and those cannot be expressed as one span per row --
    doing it per row slices the ghost into floating slabs.  Per column both
    fall out of the same loop: the top of the column follows the dome, the
    bottom follows the notch.

    Args:
        cx, cy: centre of the head in pixels.
        radius: body radius in pixels.
        color: body colour.
        facing: unit vector the eyes look along.
        phase: 0/1, which way the skirt waves this frame.
        scared: draw the frightened face instead of the hunting one.
    """
    r = radius
    body, edge = shade(color, LIT), shade(color, RIM)
    notch_w = max(2, int(round(r * 0.52)))
    notch_h = max(2, int(round(r * 0.30)))
    left = int(round(cx - r))

    for col in range(int(round(cx - r)), int(round(cx + r)) + 1):
        dx = col - cx
        # Top of the column: the dome curves in, the flanks are flat.
        rise = math.sqrt(max(0.0, r * r - dx * dx))
        top = int(round(cy - rise)) if abs(dx) < r else int(round(cy))
        # Bottom of the column: notches, phase shifting the whole pattern.
        notch = ((col - left) // notch_w + phase) % 2
        bottom = int(round(cy + r)) - (notch_h if notch else 0)
        if bottom <= top:
            continue
        screen.fill(edge, (col, top - 1, 1, bottom - top + 3))
        screen.fill(body, (col, top, 1, bottom - top))

    if scared:
        _scared_face(screen, cx, cy, r, face)
    else:
        _eyes(screen, cx, cy, r, facing, face)


def _eyes(screen: pygame.Surface, cx: int, cy: int, r: float,
          facing: tuple, white: tuple = (255, 255, 255)) -> None:
    """Two eyes whose pupils lean the way the ghost is heading."""
    pupil = (24, 26, 90)
    er, pr = r * 0.27, r * 0.135
    ex, ey = r * 0.42, -r * 0.06
    ox, oy = facing[0] * r * 0.11, facing[1] * r * 0.11
    for sign in (-1, 1):
        disc(screen, int(cx + sign * ex), int(cy + ey), er, white, rim=False)
        disc(screen, int(cx + sign * ex + ox), int(cy + ey + oy), pr, pupil,
             rim=False)


def _scared_face(screen: pygame.Surface, cx: int, cy: int,
                 r: float, white: tuple = (255, 255, 255)) -> None:
    """The panicking face: dot eyes and a wavy mouth."""
    er = max(1.0, r * 0.17)
    for sign in (-1, 1):
        disc(screen, int(cx + sign * r * 0.38), int(cy - r * 0.10), er, white,
             rim=False)
    wy = int(cy + r * 0.40)
    for i in range(5):
        x = int(cx - r * 0.60 + i * r * 0.30)
        screen.fill(white, (x, wy + (r * 0.18 if i % 2 else 0),
                            max(2, int(r * 0.22)), max(2, int(r * 0.16))))


def facing_of(entity: Mover) -> tuple:
    """Unit vector for an entity's heading, defaulting to *up* when still."""
    if entity.direction is None:
        return (0.0, -1.0)
    return (float(entity.direction.dx), float(entity.direction.dy))


class CreatureType(enum.Enum):
    """Marks what a maze cell is. Kept for the wall/empty bookkeeping."""
    WALL = "wall"
    EMPTY = "empty"
