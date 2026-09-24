"""Tests for pacman.core.maze_loader (Person A).

Read the test name, then make it pass.  Grouped by function, in the
order to implement them.

The tests that exercise the real vendored package are marked in their
docstrings; the rest are pure and need no package at all.
"""

from typing import Any

import pytest

from pacman.core.errors import MazeGenerationError
from pacman.core.maze_loader import (
    CLOSED_CELL,
    WALL_EAST,
    WALL_NORTH,
    WALL_SOUTH,
    WALL_WEST,
    _read_walls,
    cells_to_tiles,
    generate_tile_grid,
    is_closed,
)


class FakeGenerator:
    """Stand-in for the package, so the pure logic needs no wheel."""

    def __init__(self, maze: Any) -> None:
        """Hold whatever *maze* the test wants to hand back."""
        self.maze = maze


class NoMazeGenerator:
    """A build of the package that names its grid something else."""


# --------------------------------------------------------------------
# the bitmask constants -- get these wrong and everything inverts
# --------------------------------------------------------------------

def test_wall_bits_match_the_package() -> None:
    """N=1 E=2 S=4 W=8, as the package's own _braid() uses them."""
    assert (WALL_NORTH, WALL_EAST, WALL_SOUTH, WALL_WEST) == (1, 2, 4, 8)


def test_closed_cell_is_fifteen() -> None:
    """All four walls set is the package's "42" glyph."""
    assert CLOSED_CELL == 15


def test_is_closed() -> None:
    """Only a fully walled cell is closed."""
    assert is_closed(15) is True
    assert is_closed(0) is False
    assert is_closed(14) is False
    assert is_closed(7) is False


# --------------------------------------------------------------------
# cells_to_tiles -- the expansion, pure, no package needed
# --------------------------------------------------------------------

def test_tile_grid_dimensions() -> None:
    """A w x h cell grid becomes (2w+1) x (2h+1) tiles."""
    cells = [[15] * 5 for _ in range(4)]
    tiles = cells_to_tiles(cells)
    assert len(tiles) == 2 * 4 + 1
    assert all(len(row) == 2 * 5 + 1 for row in tiles)


def test_closed_cell_is_entirely_solid() -> None:
    """A single "42" cell yields a 3x3 block with no opening."""
    tiles = cells_to_tiles([[15]])
    assert all(all(row) for row in tiles)


def test_open_cell_centre_is_a_corridor() -> None:
    """Cell (cx, cy) lands on tile (2cx+1, 2cy+1), and is walkable."""
    tiles = cells_to_tiles([[0]])
    assert tiles[1][1] is False


def test_border_is_solid_even_when_a_cell_says_otherwise() -> None:
    """A cell with NO walls must still not open the outer border.

    Cell value 0 claims every side is open.  On a 1x1 maze all four of
    those sides ARE the border.  If they get carved, an entity walks
    straight off the grid and every is_wall() lookup goes out of range.
    Carve only toward a neighbour that exists.
    """
    tiles = cells_to_tiles([[0]])
    height, width = len(tiles), len(tiles[0])
    assert all(tiles[0][x] for x in range(width)), "top border"
    assert all(tiles[height - 1][x] for x in range(width)), "bottom border"
    assert all(tiles[y][0] for y in range(height)), "left border"
    assert all(tiles[y][width - 1] for y in range(height)), "right border"


def test_nothing_is_carved_toward_a_closed_cell() -> None:
    """A "42" cell stays sealed even if its neighbour disagrees.

    Here the left cell claims no east wall while the right cell is the
    glyph.  Carving on the open cell's word alone would punch a hole
    into a solid block.
    """
    tiles = cells_to_tiles([[WALL_NORTH | WALL_SOUTH | WALL_WEST, 15]])
    #                        cell (0,0): open to the EAST only
    assert tiles[1][2] is True, "the tile between the two cells"


def test_a_shared_wall_is_carved_once_from_either_side() -> None:
    """Two cells open toward each other share one passage tile."""
    left = WALL_NORTH | WALL_SOUTH | WALL_WEST     # open east
    right = WALL_NORTH | WALL_SOUTH | WALL_EAST    # open west
    tiles = cells_to_tiles([[left, right]])
    assert tiles[1][1] is False, "left cell centre"
    assert tiles[1][3] is False, "right cell centre"
    assert tiles[1][2] is False, "the passage between them"


def test_a_wall_between_two_cells_stays_solid() -> None:
    """Neither cell opens toward the other, so the wall remains."""
    left = WALL_NORTH | WALL_SOUTH | WALL_WEST | WALL_EAST
    right = WALL_NORTH | WALL_SOUTH | WALL_EAST | WALL_WEST
    tiles = cells_to_tiles([[left, right]])
    assert tiles[1][2] is True


def test_vertical_passage_uses_the_south_bit() -> None:
    """A cell open to the south connects to the cell below it."""
    top = WALL_NORTH | WALL_EAST | WALL_WEST       # open south
    bottom = WALL_SOUTH | WALL_EAST | WALL_WEST    # open north
    tiles = cells_to_tiles([[top], [bottom]])
    assert tiles[2][1] is False, "the passage between the rows"


def test_even_even_tiles_are_always_wall() -> None:
    """A tile at two even coordinates is a post nothing can carve.

    It sits at the corner of four cells, so no single wall bit owns it.
    """
    cells = [[0] * 3 for _ in range(3)]
    tiles = cells_to_tiles(cells)
    for y in range(0, len(tiles), 2):
        for x in range(0, len(tiles[0]), 2):
            assert tiles[y][x] is True, f"tile ({x}, {y})"


def test_cells_to_tiles_rejects_an_empty_grid() -> None:
    """An empty grid is a package failure, not a 1x1 maze."""
    with pytest.raises(MazeGenerationError):
        cells_to_tiles([])


def test_cells_to_tiles_rejects_an_empty_row() -> None:
    """A grid of empty rows has no width to expand."""
    with pytest.raises(MazeGenerationError):
        cells_to_tiles([[]])


# --------------------------------------------------------------------
# _read_walls -- never trust the package's shape
# --------------------------------------------------------------------

def test_read_walls_returns_the_grid() -> None:
    """A well-formed grid of the asked-for size passes through."""
    grid = [[9, 3], [12, 6]]
    assert _read_walls(FakeGenerator(grid), 2, 2) == grid


def test_read_walls_copies_the_grid() -> None:
    """The result must not alias the package's own lists.

    Mutating what we return must not reach back into the generator.
    """
    grid = [[9, 3], [12, 6]]
    out = _read_walls(FakeGenerator(grid), 2, 2)
    out[0][0] = 0
    assert grid[0][0] == 9


def test_read_walls_rejects_a_missing_attribute() -> None:
    """Another group's build may not call it `maze`."""
    with pytest.raises(MazeGenerationError):
        _read_walls(NoMazeGenerator(), 2, 2)


def test_read_walls_rejects_the_wrong_height() -> None:
    """size=(1, 1) really does come back as a 2x2 grid."""
    with pytest.raises(MazeGenerationError):
        _read_walls(FakeGenerator([[9, 3], [12, 6]]), 1, 1)


def test_read_walls_rejects_the_wrong_width() -> None:
    """Rows shorter or longer than asked for are a failure."""
    with pytest.raises(MazeGenerationError):
        _read_walls(FakeGenerator([[9, 3, 1], [12, 6, 4]]), 2, 2)


def test_read_walls_rejects_a_ragged_grid() -> None:
    """Rows of differing length would crash later, out of context."""
    with pytest.raises(MazeGenerationError):
        _read_walls(FakeGenerator([[9, 3], [12]]), 2, 2)


def test_read_walls_rejects_a_non_list() -> None:
    """`maze` being a string or None is not a grid."""
    for bad in ("not a grid", None, 42):
        with pytest.raises(MazeGenerationError):
            _read_walls(FakeGenerator(bad), 2, 2)


def test_read_walls_rejects_an_out_of_range_value() -> None:
    """A bitmask outside 0..15 means the encoding is not what we think."""
    with pytest.raises(MazeGenerationError):
        _read_walls(FakeGenerator([[9, 99], [12, 6]]), 2, 2)
    with pytest.raises(MazeGenerationError):
        _read_walls(FakeGenerator([[9, -1], [12, 6]]), 2, 2)


def test_read_walls_rejects_a_non_int_value() -> None:
    """Including bool, since isinstance(True, int) is True."""
    with pytest.raises(MazeGenerationError):
        _read_walls(FakeGenerator([[9, "3"], [12, 6]]), 2, 2)
    with pytest.raises(MazeGenerationError):
        _read_walls(FakeGenerator([[9, True], [12, 6]]), 2, 2)


# --------------------------------------------------------------------
# generate_tile_grid -- against the real vendored package
# --------------------------------------------------------------------

def test_generate_tile_grid_shape() -> None:
    """Uses the real package: the grid is (2h+1) x (2w+1)."""
    tiles = generate_tile_grid(8, 6, seed=1)
    assert len(tiles) == 2 * 6 + 1
    assert all(len(row) == 2 * 8 + 1 for row in tiles)


def test_generate_tile_grid_has_corridors_and_walls() -> None:
    """Uses the real package: a maze is not all one or all the other."""
    tiles = generate_tile_grid(8, 6, seed=1)
    flat = [t for row in tiles for t in row]
    assert any(flat), "some walls"
    assert not all(flat), "some corridors"


def test_generate_tile_grid_border_is_solid() -> None:
    """Uses the real package: nothing may walk off the grid."""
    tiles = generate_tile_grid(8, 6, seed=1)
    height, width = len(tiles), len(tiles[0])
    assert all(tiles[0])
    assert all(tiles[height - 1])
    assert all(tiles[y][0] for y in range(height))
    assert all(tiles[y][width - 1] for y in range(height))


def test_generate_tile_grid_is_reproducible() -> None:
    """Uses the real package: the same seed gives the same maze.

    Subject VI.1 needs level 1 identical on every run.
    """
    assert generate_tile_grid(8, 6, seed=7) == \
        generate_tile_grid(8, 6, seed=7)


def test_generate_tile_grid_differs_by_seed() -> None:
    """Uses the real package: later levels must not all look alike."""
    grids = {
        tuple(tuple(row) for row in generate_tile_grid(10, 8, seed=s))
        for s in (1, 2, 3, 4, 5)
    }
    assert len(grids) > 1


def test_generate_tile_grid_handles_the_42_glyph() -> None:
    """Uses the real package: the level-1 size contains solid cells.

    On 14x10 with seed 42 the glyph is an 18-cell blob.  Those cells
    must come through as solid interior tiles -- which is also why
    level.create_level has to seal what they cut off.
    """
    tiles = generate_tile_grid(14, 10, seed=42)
    interior_walls = sum(
        1
        for y in range(1, len(tiles) - 1)
        for x in range(1, len(tiles[0]) - 1)
        if tiles[y][x] and y % 2 == 1 and x % 2 == 1
    )
    assert interior_walls > 0, "odd/odd tiles are cells; some are solid"


@pytest.mark.parametrize("width,height", [(0, 0), (-5, 10), (10, -5),
                                          (0, 10), (1, 1)])
def test_generate_tile_grid_rejects_bad_sizes(width: int,
                                              height: int) -> None:
    """Uses the real package: raw IndexError must never escape.

    size=(0, 0) and negative sizes raise IndexError from inside the
    package; size=(1, 1) returns a wrong-shaped 2x2 grid.  All of them
    must arrive as MazeGenerationError.
    """
    with pytest.raises(MazeGenerationError):
        generate_tile_grid(width, height, seed=1)
