"""Tests for pacman.core.ghost_ai (Person A).

Hand-drawn levels ('#' wall, '.' corridor); the player and ghosts are
placed by hand so every decision is predictable.
"""

import random

from pacman.core.entities import (
    Direction, Ghost, GhostState, Personality, Player,
)
from pacman.core.ghost_ai import (
    SHY_DISTANCE, chase_target, choose_ghost_direction, manhattan,
)
from pacman.core.level import Level, Point


def make_level(*rows: str) -> Level:
    """Build a Level from text rows: '#' is a wall, anything else open."""
    return Level([[c == "#" for c in row] for row in rows], 1, 1)


HALL = make_level(
    "#########",
    "#.......#",
    "#########",
)

FORK = make_level(
    "#####",
    "#...#",
    "#.#.#",
    "#...#",
    "#####",
)


def ghost_at(tile: Point, personality: Personality = Personality.CHASER,
             state: GhostState = GhostState.NORMAL) -> Ghost:
    """Build a ghost standing on *tile* in *state*."""
    ghost = Ghost(tile, 4.0, personality)
    ghost.state = state
    return ghost


def test_manhattan() -> None:
    """Distance is |dx| + |dy|."""
    assert manhattan((1, 1), (4, 5)) == 7
    assert manhattan((2, 2), (2, 2)) == 0


def test_chaser_targets_player() -> None:
    """Blinky aims at the player's tile."""
    player = Player((5, 1), 5.0, 3)
    assert chase_target(ghost_at((1, 1)), HALL, player) == (5, 1)


def test_ambusher_aims_ahead() -> None:
    """Pinky aims four tiles ahead, clamped to an open tile."""
    player = Player((2, 1), 5.0, 3)
    player.direction = Direction.RIGHT
    ghost = ghost_at((8, 1), Personality.AMBUSHER)
    assert chase_target(ghost, HALL, player) == (6, 1)


def test_ambusher_without_direction_targets_player() -> None:
    """A player who has not moved yet is targeted directly."""
    player = Player((2, 1), 5.0, 3)
    ghost = ghost_at((8, 1), Personality.AMBUSHER)
    assert chase_target(ghost, HALL, player) == (2, 1)


def test_shy_retreats_when_close_and_chases_when_far() -> None:
    """Clyde goes home inside SHY_DISTANCE, else chases."""
    wide = make_level("#" * 22, "#" + "." * 20 + "#", "#" * 22)
    player = Player((1, 1), 5.0, 3)
    near = ghost_at((1 + SHY_DISTANCE, 1), Personality.SHY)
    near.home = (20, 1)
    far = ghost_at((1 + SHY_DISTANCE + 1, 1), Personality.SHY)
    far.home = (20, 1)
    assert chase_target(near, wide, player) == (20, 1)
    assert chase_target(far, wide, player) == (1, 1)


def test_eaten_ghost_stays() -> None:
    """An eaten ghost has no direction."""
    ghost = ghost_at((4, 1), state=GhostState.EATEN)
    player = Player((1, 1), 5.0, 3)
    assert choose_ghost_direction(ghost, HALL, player,
                                  random.Random(0)) is None


def test_walled_in_ghost_stays() -> None:
    """A ghost with no open neighbour returns None."""
    level = make_level("###", "#.#", "###")
    player = Player((1, 1), 5.0, 3)
    assert choose_ghost_direction(ghost_at((1, 1)), level, player,
                                  random.Random(0)) is None


def test_chase_moves_toward_player() -> None:
    """In a hall the chasing ghost walks toward the player."""
    player = Player((1, 1), 5.0, 3)
    got = choose_ghost_direction(ghost_at((6, 1)), HALL, player,
                                 random.Random(0))
    assert got is Direction.LEFT


def test_frightened_ghost_flees() -> None:
    """A frightened ghost walks away (random 15 % excluded by seed)."""
    player = Player((1, 1), 5.0, 3)
    ghost = ghost_at((4, 1), state=GhostState.FRIGHTENED)
    for seed in range(20):
        rng = random.Random(seed)
        if rng.random() < 0.15:
            continue
        assert choose_ghost_direction(
            ghost, HALL, player, random.Random(seed)) is Direction.RIGHT


def test_no_u_turn_unless_dead_end() -> None:
    """The ghost keeps going forward even if the player is behind it."""
    player = Player((1, 1), 5.0, 3)
    ghost = ghost_at((4, 1))
    ghost.direction = Direction.RIGHT
    assert choose_ghost_direction(ghost, HALL, player,
                                  random.Random(0)) is Direction.RIGHT
    end = ghost_at((7, 1))
    end.direction = Direction.RIGHT
    assert choose_ghost_direction(end, HALL, player,
                                  random.Random(0)) is Direction.LEFT


def test_choice_is_always_open() -> None:
    """Whatever the state or whim, the direction leads into a corridor."""
    player = Player((3, 3), 5.0, 3)
    rng = random.Random(3)
    for personality in Personality:
        for state in (GhostState.NORMAL, GhostState.FRIGHTENED):
            ghost = ghost_at((1, 1), personality, state)
            for _ in range(30):
                way = choose_ghost_direction(ghost, FORK, player, rng)
                assert way is not None
                assert FORK.is_open(*way.step(ghost.tile))


def test_scattering_ghost_heads_for_its_corner() -> None:
    """In scatter the player is ignored and the home corner is the goal."""
    ghost = ghost_at((4, 1))
    ghost.home = (1, 1)
    player = Player((7, 1), 5.0, 3)
    rng = random.Random(1)
    assert choose_ghost_direction(
        ghost, HALL, player, rng, scatter=True) is Direction.LEFT
    assert choose_ghost_direction(
        ghost, HALL, player, rng, scatter=False) is Direction.RIGHT
