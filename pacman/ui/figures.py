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
# The arcade sprite, kept as a bitmap: a fixed 14x14 grid of square pixels
# (stepped dome head, straight sides, three jagged feet).  Every grid cell
# is stamped as one solid block, so the sprite keeps its hard 8-bit edges:
# no outline, no highlight, no shading, flat colour only.
_PUPIL = (30, 30, 120)
_WHITE = (255, 255, 255)

#: Width and height of the sprite's grid, in cells.
_GRID = 14

# Head and body, rows 0..11: flat in the centre of the top, stepping out
# in blocky pixels to the full width, then straight down.
_BODY_ROWS = (
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
)

# The hem, rows 12..13: always exactly three feet and two notches.  A notch
# is one cell wide on its upper row and three on its lower one, so the
# feet are chunky blocks that taper a little towards the floor.  The second
# frame moves the notches one step, which is the arcade's walking wobble.
_HEM_FRAMES = (
    ("####.####.####",
     "###...##...###"),
    ("###.####.#####",
     "##...####...##"),
)

# The hunting eye: a white block 4 cells wide and 5 tall, with a 2x2
# dark-blue pupil that slides one step inside it towards the heading.
_EYE_SHAPE = (
    "####",
    "####",
    "####",
    "####",
    "####",
)
_EYE_COLS = (2, 8)   # left column of each eye (symmetrical on 14 cells)
_EYE_TOP = 3         # top row of the eyes, in the upper half of the face

# The frightened face: two 2x2 square eyes over a zigzag mouth, stamped
# in the caller's face colour the way the arcade draws it on the blue body.
_FRIGHT_EYES = tuple((gy, gx) for gy in (5, 6) for gx in (3, 4, 9, 10))
_FRIGHT_MOUTH = (
    tuple((9, gx) for gx in (2, 3, 6, 7, 10, 11))
    + tuple((10, gx) for gx in (1, 4, 5, 8, 9, 12))
)


def _sign(value: float) -> int:
    """-1, 0 or 1, with a dead zone so a near-zero heading counts as still."""
    return (value > 0.3) - (value < -0.3)


def _edges(side: int, cells: int) -> list[int]:
    """Pixel boundary of each of *cells* divisions across *side* pixels.

    Nearest-neighbour scaling, used only when the caller does not pick a
    whole-pixel cell size: integer cell edges over the whole sprite, so a
    cramped corridor still gets a full-size blocky ghost.
    """
    return [round(i * side / cells) for i in range(cells + 1)]


def _stamp_rows(screen: pygame.Surface, rows: tuple[str, ...],
                left: int, top: int, cut: list[int],
                color: Color) -> None:
    """Stamp every run of ``#`` in *rows* as one rectangle per run."""
    for gy, row in enumerate(rows):
        gx = 0
        while gx < len(row):
            if row[gx] != "#":
                gx += 1
                continue
            end = gx
            while end < len(row) and row[end] == "#":
                end += 1
            screen.fill(color, (left + cut[gx], top + cut[gy],
                                cut[end] - cut[gx],
                                cut[gy + 1] - cut[gy]))
            gx = end


def _stamp_cells(screen: pygame.Surface,
                 cells: tuple[tuple[int, int], ...],
                 left: int, top: int, cut: list[int],
                 color: Color) -> None:
    """Stamp each ``(row, column)`` cell as one solid block."""
    for gy, gx in cells:
        screen.fill(color, (left + cut[gx], top + cut[gy],
                            cut[gx + 1] - cut[gx],
                            cut[gy + 1] - cut[gy]))


def ghost(screen: pygame.Surface, cx: int, cy: int, radius: float,
          color: Color, facing: Vec = (0, -1), phase: int = 0,
          scared: bool = False, face: Color = (255, 255, 255),
          pixel: int = 0, eyes_only: bool = False) -> None:
    """Stamp the ghost, centred on ``(cx, cy)``.

    Args:
        cx, cy: centre in pixels.
        radius: half the sprite's side in pixels.  Ignored when *pixel*
            is given.
        color: body colour.
        facing: heading; the pupils lean that way.  ``(0, 0)`` leaves
            them dead centre, looking straight out.
        phase: 0/1, which frame of the hem to draw this frame.
        scared: draw the frightened face instead of the hunting eyes.
        face: colour of the frightened eyes and mouth.
        pixel: side in screen pixels of one sprite cell.  When positive
            the sprite is exactly ``14 * pixel`` pixels wide and every
            cell is the same size, which is the faithful arcade look.
            When 0 the cells are scaled to fit *radius* instead.
        eyes_only: draw just the eyes, which is what an eaten ghost looks
            like on its way home.
    """
    rows = _BODY_ROWS + _HEM_FRAMES[int(phase) % 2]
    if pixel > 0:
        side = _GRID * pixel
        cut = [i * pixel for i in range(_GRID + 1)]
        left, top = cx - side // 2, cy - side // 2
    else:
        r = max(2, int(round(radius)))
        side = 2 * r + 1
        cut = _edges(side, _GRID)
        left, top = cx - side // 2, cy - side // 2
    if not eyes_only:
        _stamp_rows(screen, rows, left, top, cut, color)
    if scared and not eyes_only:
        _stamp_cells(screen, _FRIGHT_EYES + _FRIGHT_MOUTH,
                     left, top, cut, face)
        return
    dx, dy = _sign(facing[0]), _sign(facing[1])
    whites = tuple((_EYE_TOP + gy, base + gx)
                   for base in _EYE_COLS
                   for gy, line in enumerate(_EYE_SHAPE)
                   for gx, ch in enumerate(line) if ch == "#")
    # 2x2 pupil: centred in the eye at (row 2, column 1) and sliding one
    # step towards the heading.
    pupils = tuple((_EYE_TOP + 2 + dy + r_, base + 1 + dx + c_)
                   for base in _EYE_COLS
                   for r_ in (0, 1) for c_ in (0, 1))
    _stamp_cells(screen, whites, left, top, cut, _WHITE)
    _stamp_cells(screen, pupils, left, top, cut, _PUPIL)


def facing_of(entity: Mover) -> Vec:
    """Unit vector for an entity's heading, defaulting to *up* when still."""
    if entity.direction is None:
        return (0.0, -1.0)
    return (float(entity.direction.dx), float(entity.direction.dy))


class CreatureType(enum.Enum):
    """Marks what a maze cell is. Kept for the wall/empty bookkeeping."""
    WALL = "wall"
    EMPTY = "empty"
