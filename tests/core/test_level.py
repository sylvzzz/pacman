"""Tests for pacman.core.level (Person A).

Hand-drawn levels ('#' wall, '.' corridor) cover the pure logic;
``create_level`` runs against the real vendored maze package.
"""

import random

import pytest

from pacman.core.config import LevelSpec
from pacman.core.level import MAX_CACHED_DISTANCE_MAPS, Level, create_level


def make_level(*rows: str) -> Level:
    """Build a Level from text rows: '#' is a wall, anything else open."""
    return Level([[c == "#" for c in row] for row in rows], 1, 1)


ROOM = make_level(
    "#####",
    "#...#",
    "#.#.#",
    "#...#",
    "#####",
)


def test_is_open_inside_and_walls() -> None:
    """Corridors are open, walls are not."""
    assert ROOM.is_open(1, 1)
    assert not ROOM.is_open(0, 0)
    assert not ROOM.is_open(2, 2)


@pytest.mark.parametrize("x, y", [(-1, 1), (1, -1), (5, 1), (1, 5)])
def test_is_open_outside_grid(x: int, y: int) -> None:
    """Anything off the grid is closed, never an IndexError."""
    assert not ROOM.is_open(x, y)


def test_open_tiles_count_and_order() -> None:
    """Open tiles come back in row order."""
    tiles = ROOM.open_tiles()
    assert len(tiles) == 8
    assert tiles == sorted(tiles, key=lambda t: (t[1], t[0]))


def test_neighbours_have_no_diagonals() -> None:
    """Only the four orthogonal open tiles are neighbours."""
    assert sorted(ROOM.neighbours((1, 1))) == [(1, 2), (2, 1)]


def test_distances_follow_corridors() -> None:
    """Around the pillar, (1, 1) to (3, 3) is 4 steps, not 2."""
    dist = ROOM.distances_from((1, 1))
    assert dist[(1, 1)] == 0
    assert dist[(3, 3)] == 4


def test_distances_omit_unreachable_and_wall_start() -> None:
    """A walled-off tile is absent; a wall start gives an empty map."""
    level = make_level("#####", "#.#.#", "#####")
    assert (3, 1) not in level.distances_from((1, 1))
    assert level.distances_from((0, 0)) == {}


def test_distances_are_cached() -> None:
    """Asking twice returns the very same map object."""
    assert ROOM.distances_from((1, 1)) is ROOM.distances_from((1, 1))


def test_distance_cache_is_capped() -> None:
    """The cache never grows past its cap."""
    level = make_level("#" * 5, "#...#", "#####")
    for i in range(MAX_CACHED_DISTANCE_MAPS + 5):
        level.distances_from((i + 10, 10))
    assert len(level._distance_cache) <= MAX_CACHED_DISTANCE_MAPS


def test_nearest_open_prefers_closest() -> None:
    """A wall target resolves to an adjacent corridor."""
    assert ROOM.nearest_open((0, 0)) == (1, 1)
    assert ROOM.nearest_open((3, 3)) == (3, 3)


def test_nearest_open_without_tiles_raises() -> None:
    """A solid maze has nowhere to put anything."""
    with pytest.raises(ValueError):
        make_level("###", "###").nearest_open((1, 1))


def test_prune_unreachable_seals_pockets() -> None:
    """Tiles cut off from the start become walls and the cache resets."""
    level = make_level("#######", "#.#.#.#", "#######")
    level.distances_from((1, 1))
    assert level.prune_unreachable((1, 1)) == 2
    assert level.open_tiles() == [(1, 1)]
    assert level.distances_from((1, 1)) == {(1, 1): 0}


def test_corner_tiles_reading_order() -> None:
    """Corners are NW, NE, SW, SE."""
    assert ROOM.corner_tiles() == [(0, 0), (4, 0), (0, 4), (4, 4)]


def test_pellets_left_counts_both_kinds() -> None:
    """Small and power pellets both count."""
    level = make_level("###", "#.#", "###")
    level.pacgums.add((1, 1))
    level.super_pacgums.add((2, 2))
    assert level.pellets_left() == 2


# --- create_level on the real package -----------------------------------

SPEC = LevelSpec(10, 8)


def test_create_level_is_reproducible() -> None:
    """Same seed and rng seed give the same level."""
    a = create_level(SPEC, 1, 42, 80, random.Random(7))
    b = create_level(SPEC, 1, 42, 80, random.Random(7))
    assert a.grid == b.grid
    assert a.pacgums == b.pacgums
    assert a.player_spawn == b.player_spawn


def test_create_level_places_everything_reachable() -> None:
    """Spawns, ghosts and pellets are all reachable from the player."""
    level = create_level(SPEC, 3, 42, 100, random.Random(1))
    reach = level.distances_from(level.player_spawn)
    assert level.number == 3
    assert len(level.ghost_spawns) == 4
    assert len(set(level.ghost_spawns)) == 4
    assert level.player_spawn not in level.ghost_spawns
    assert set(level.ghost_spawns) == level.super_pacgums
    assert level.pacgums
    for tile in level.pacgums | level.super_pacgums:
        assert tile in reach
    assert level.player_spawn not in level.pacgums


def test_create_level_density_zero_has_no_pacgums() -> None:
    """Density 0 places only the power pellets."""
    level = create_level(SPEC, 1, 42, 0, random.Random(1))
    assert not level.pacgums
    assert level.pellets_left() == 4
