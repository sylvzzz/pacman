"""Adapter around the assigned A-Maze-ing package.

Contents: _load_generator_class(), _generate(), _read_walls(),
  is_closed(), cells_to_tiles(), generate_tile_grid().

This is the **only** module in the project allowed to import
``mazegenerator`` (see CLAUDE.md).  Subject V.4 requires the assigned
package to be used unmodified, and it will be re-installed during the
peer review, so every assumption about its interface lives here and
nowhere else.  If a reviewer swaps in another group's build, this file
is the only one that changes.

What the package gives us, verified against mazegenerator 2.1.0:

* ``MazeGenerator(size=(w, h), perfect=False, seed=n)`` then ``gen.maze``
  is a ``list[list[int]]`` indexed ``maze[y][x]`` -- one bitmask per
  CELL, not per tile.
* **A set bit means that wall is PRESENT**, not that the way is open.
  Confirmed from the package's own ``_braid()``, which treats a cell
  with three or more bits set as a dead end and opens a passage with
  ``&= ~code``.  A corridor opening is therefore ``not (cell & bit)``.
* ``perfect=False`` runs ``_braid()``, which removes dead ends, so
  corridors loop and a chased player is never trapped.
* Value 15 -- all four walls -- is the package's decorative "42" glyph.
  Those cells are solid.  On a 14x10 maze with seed 42 they form an
  18-cell blob across the middle, right where the player spawns.
* It cannot be trusted about its own shape: ``size=(1, 1)`` returns a
  2x2 grid.  Validate what comes back.
* Bad sizes raise a raw ``IndexError`` from inside the package, and it
  prints ``MazeGenerator Warning: ...`` to stdout, which we cannot
  switch off.
* Seed 0 means "pick a random seed" to the package, so callers must
  pass >= 1.  ``config`` guarantees this for level 1 and ``level`` must
  do the same for later levels.
"""

from typing import Any

from .errors import MazeGenerationError

# Wall bitmask, as the package defines it.  A SET bit is a wall.
WALL_NORTH = 1
WALL_EAST = 2
WALL_SOUTH = 4
WALL_WEST = 8

# All four walls set: the package's "42" glyph.  A solid, sealed cell.
CLOSED_CELL = WALL_NORTH | WALL_EAST | WALL_SOUTH | WALL_WEST

# (dx, dy, wall bit) for each side of a cell.
NEIGHBOURS = (
    (0, -1, WALL_NORTH),
    (1, 0, WALL_EAST),
    (0, 1, WALL_SOUTH),
    (-1, 0, WALL_WEST),
)


def _load_generator_class() -> Any:
    """Import the assigned package and return its MazeGenerator class.

    Imported inside the function, not at module level, so a missing or
    broken package becomes a MazeGenerationError the user can read
    instead of a traceback at startup.

    Returns:
        Any: the package's generator class.  Untyped on purpose -- the
            package ships no ``py.typed``, so everything it hands back
            is ``Any`` and gets re-validated in ``_read_walls``.

    Raises:
        MazeGenerationError: the package is missing or has no
            MazeGenerator.
    """
    try:
        from mazegenerator import (  # type: ignore[import-untyped]
            MazeGenerator,
        )
    except ImportError as e:
        raise MazeGenerationError(
            "the maze generator package is not installed; "
            "run `make install`"
        ) from e
    return MazeGenerator


def _generate(width: int, height: int, seed: int) -> Any:
    """Build one generator for a *width* x *height* maze.

    ``perfect=False`` is mandatory (subject V.4): it is what produces
    Pac-Man-compatible looping corridors instead of a perfect maze full
    of dead ends.

    Args:
        width: maze width in cells.
        height: maze height in cells.
        seed: must be >= 1; the package reads 0 as "random".

    Returns:
        Any: the constructed generator instance.

    Raises:
        MazeGenerationError: the package raised anything at all.
    """
    # TODO (you):
    # 1. generator_class = _load_generator_class().
    # 2. Inside a try, construct it with KEYWORD arguments:
    #        generator_class(size=(width, height), perfect=False,
    #                        seed=seed)
    #    Keywords, not positions, so a reordered signature in another
    #    group's build fails loudly instead of silently swapping width
    #    for height.
    # 3. except Exception as e -> raise MazeGenerationError from e.
    #    A broad `except Exception` is right here and nowhere else in
    #    core: this is third-party code, size=(0, 0) raises a raw
    #    IndexError from inside it, and you cannot enumerate what a
    #    package you did not write throws.  Name width, height and seed
    #    in the message so the failing level is identifiable.
    # 4. Return the instance.
    #
    # Optional, worth considering: the package prints "MazeGenerator
    # Warning: ..." to stdout.  contextlib.redirect_stdout around the
    # construction would keep our own output clean.  Your call --
    # document whichever you choose.
    raise NotImplementedError("_generate")


def _read_walls(generator: Any, width: int, height: int) -> list[list[int]]:
    """Return *generator*'s cell grid, validated and copied.

    Never trust the package's shape: ``size=(1, 1)`` gives back a 2x2
    grid.  Everything downstream indexes this by ``[y][x]`` assuming it
    is exactly *height* rows of *width* cells, so that is checked here.

    The values are copied into a fresh ``list[list[int]]`` rather than
    returned as-is, so nothing later can mutate the package's own state
    and no untyped value escapes this module.

    Args:
        generator: the object returned by ``_generate``.
        width: the width that was asked for, in cells.
        height: the height that was asked for, in cells.

    Returns:
        A *height* x *width* grid of wall bitmasks, each 0..15.

    Raises:
        MazeGenerationError: no usable ``maze`` attribute, the wrong
            shape, a ragged row, or a value outside 0..15.
    """
    # TODO (you):
    # 1. Read generator.maze inside a try; `except AttributeError` ->
    #    MazeGenerationError (another group's build may name it
    #    differently, and that must be a clear message).
    # 2. Check it is a list of `height` rows -> else MazeGenerationError
    #    naming both the asked-for and the returned size.
    # 3. Build the result row by row.  For each row: check it is a list
    #    of `width` items (a ragged grid is a package bug, not yours),
    #    and check every item is an int in 0..15 -- remember
    #    isinstance(True, int) is True, so reject bool here too, exactly
    #    as _pick_int does.
    # 4. Return the new grid.
    raise NotImplementedError("_read_walls")


def is_closed(cell: int) -> bool:
    """Return True when *cell* is sealed on all four sides.

    These are the package's "42" glyph cells.  They are not corridors
    and nothing may be carved into or out of them.
    """
    # TODO (you): one comparison against CLOSED_CELL.
    raise NotImplementedError("is_closed")


def cells_to_tiles(cells: list[list[int]]) -> list[list[bool]]:
    """Expand a cell bitmask grid into a wall grid of tiles.

    A ``w`` x ``h`` cell grid becomes ``(2w+1)`` x ``(2h+1)`` tiles.
    Cell ``(cx, cy)`` sits at tile ``(2cx+1, 2cy+1)`` -- always odd.
    Even coordinates are the space *between* cells, which is either a
    carved passage or solid wall, and the outermost ring is the border.
    That is where the ``+1`` comes from.

    A cell has no thickness, so a wall between two cells has no
    position in the cell grid -- it is only a bit. Entities move at
    float positions and collide with tiles, so the wall has to become a
    real place. That is the whole reason this function exists.

    Two rules that do not come from the bitmasks and must hold anyway:

    * **The border is always solid.** A passage is carved only when the
      neighbour cell is inside the grid, so a malformed cell claiming it
      has no north wall on row 0 cannot open a hole in the outer wall
      for the player to walk through.
    * **Nothing is carved toward a closed cell.** A "42" cell stays
      sealed even if its neighbour's bitmask disagrees.

    Args:
        cells: a ``height`` x ``width`` grid of bitmasks, ``[y][x]``.

    Returns:
        ``(2h+1)`` x ``(2w+1)`` grid of bools, ``[y][x]``, True = wall.

    Raises:
        MazeGenerationError: *cells* is empty.
    """
    # TODO (you):
    # 1. Guard: empty grid (or an empty first row) -> MazeGenerationError.
    # 2. height = len(cells); width = len(cells[0]).
    # 3. Start with EVERYTHING solid:
    #        tiles = [[True] * (2 * width + 1)
    #                 for _ in range(2 * height + 1)]
    #    Carving out of a solid block is safer than walling in an empty
    #    one -- a tile you forget stays a wall, which is survivable; a
    #    tile you forget the other way is a hole to walk through.
    # 4. For each cell (cx, cy): if is_closed(cell) -> `continue`,
    #    leaving its own tile solid too.  Otherwise open its centre:
    #        tiles[2 * cy + 1][2 * cx + 1] = False
    # 5. For each (dx, dy, bit) in NEIGHBOURS: carve the tile between
    #    the two cells only when ALL of these hold:
    #      - the bit is clear:  not (cell & bit)     <- open, remember
    #      - the neighbour is inside the grid        <- keeps the border
    #      - the neighbour is not is_closed(...)     <- keeps 42 sealed
    #    The tile between them is at
    #        tiles[2 * cy + 1 + dy][2 * cx + 1 + dx]
    # 6. Return tiles.
    raise NotImplementedError("cells_to_tiles")


def generate_tile_grid(width: int, height: int,
                       seed: int) -> list[list[bool]]:
    """Generate one level's wall grid, in tiles.

    The only function the rest of ``core`` calls.  ``level.create_level``
    uses it and never learns that a maze package exists.

    Args:
        width: maze width in cells.
        height: maze height in cells.
        seed: must be >= 1; 0 means "random" to the package.

    Returns:
        ``(2*height+1)`` x ``(2*width+1)`` grid of bools, True = wall.

    Raises:
        MazeGenerationError: any failure, at any stage.
    """
    # TODO (you): three lines -- _generate(), _read_walls(),
    # cells_to_tiles().  Every one of them already raises
    # MazeGenerationError and nothing else, so there is nothing to
    # catch here.
    raise NotImplementedError("generate_tile_grid")
