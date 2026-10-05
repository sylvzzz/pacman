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


# --- The arcade ghost -----------------------------------------------------
#
# A 14x14 bitmap: 12 rows of dome and flanks, then a 2-row skirt that
# alternates between two frames to make it wave.  '#' is body, '.' is empty.
GHOST_GRID = 14

_GHOST_BODY = [
    "....######....",
    "..##########..",
    ".############.",
    ".############.",
    "##############",
    "##############",
    "##############",
    "##############",
    "##############",
    "##############",
    "##############",
    "##############",
]
_GHOST_SKIRT = [
    ["###..####..###",
     "##...####...##"],
    ["#.###.##.###.#",
     "..##.####.##.."],
]

# Hunting eye: a 4x5 white block with the corners cut off.
_EYE = [".##.",
        "####",
        "####",
        "####",
        ".##."]
_EYE_COLS = (2, 8)
_EYE_ROW = 3
_PUPIL = (33, 33, 222)
_WHITE = (255, 255, 255)


def _sign(value: float) -> int:
    """-1, 0 or 1, with a dead zone so a near-zero heading counts as still."""
    return (value > 0.3) - (value < -0.3)


def _block(screen: pygame.Surface, left: float, top: float, s: float,
           c0: int, r0: int, c1: int, r1: int, color: tuple) -> None:
    """Fill the sprite-grid rectangle ``[c0, c1) x [r0, r1)``.

    Edges come from one rounding function of the grid line, so two blocks
    that touch on the grid always touch on screen: no seams at any scale.
    """
    x0, x1 = round(left + c0 * s), round(left + c1 * s)
    y0, y1 = round(top + r0 * s), round(top + r1 * s)
    screen.fill(color, (x0, y0, max(1, x1 - x0), max(1, y1 - y0)))


def _rows(screen: pygame.Surface, left: float, top: float, s: float,
          rows: list, first_row: int, color: tuple) -> None:
    """Stamp a list of bitmap rows, merging each row into horizontal runs."""
    for r, line in enumerate(rows):
        c = 0
        while c < GHOST_GRID:
            if line[c] != "#":
                c += 1
                continue
            start = c
            while c < GHOST_GRID and line[c] == "#":
                c += 1
            _block(screen, left, top, s, start, first_row + r, c,
                   first_row + r + 1, color)


def ghost(screen: pygame.Surface, cx: int, cy: int, radius: float,
          color: tuple, facing: tuple = (0, -1), phase: int = 0,
          scared: bool = False, face: tuple = (255, 255, 255),
          pixel: int = 0, eyes_only: bool = False) -> None:
    """Stamp the arcade ghost, centred on ``(cx, cy)``.

    The sprite is a square ``2 * radius`` on a side.

    Args:
        cx, cy: centre in pixels.
        radius: half the sprite's side in pixels.
        color: body colour.
        facing: heading; the pupils lean that way.
        phase: 0/1, which way the skirt waves this frame.
        scared: draw the frightened face instead of the hunting eyes.
        face: colour of the frightened eyes and mouth.
        pixel: ignored; kept so older call sites keep working.  The sprite
            is always the arcade bitmap now.
        eyes_only: draw just the eyes, which is what an eaten ghost looks
            like on its way home.
    """
    s = 2.0 * radius / GHOST_GRID
    left, top = cx - radius, cy - radius

    if not eyes_only:
        _rows(screen, left, top, s, _GHOST_BODY, 0, color)
        _rows(screen, left, top, s, _GHOST_SKIRT[int(phase) % 2],
              len(_GHOST_BODY), color)

    if scared and not eyes_only:
        # Two small square eyes and a zigzag mouth.
        _block(screen, left, top, s, 4, 5, 6, 7, face)
        _block(screen, left, top, s, 8, 5, 10, 7, face)
        for c in (2, 4, 6, 8, 10):
            _block(screen, left, top, s, c, 9, c + 1, 10, face)
        for c in (3, 5, 7, 9, 11):
            _block(screen, left, top, s, c, 10, c + 1, 11, face)
        return

    dx, dy = _sign(facing[0]), _sign(facing[1])
    for ec in _EYE_COLS:
        for r, line in enumerate(_EYE):
            for c, ch in enumerate(line):
                if ch == "#":
                    _block(screen, left, top, s, ec + c, _EYE_ROW + r,
                           ec + c + 1, _EYE_ROW + r + 1, _WHITE)
        # Pupil is 2x2 inside the 4x5 eye: 3 columns, 3 usable rows.
        pc = ec + 1 + dx
        pr = _EYE_ROW + (0 if dy < 0 else 1 if dy == 0 else 3)
        _block(screen, left, top, s, pc, pr, pc + 2, pr + 2, _PUPIL)


def facing_of(entity: Mover) -> tuple:
    """Unit vector for an entity's heading, defaulting to *up* when still."""
    if entity.direction is None:
        return (0.0, -1.0)
    return (float(entity.direction.dx), float(entity.direction.dy))


class CreatureType(enum.Enum):
    """Marks what a maze cell is. Kept for the wall/empty bookkeeping."""
    WALL = "wall"
    EMPTY = "empty"