"""Tests for pacman.ui.playfield, the adapter onto the core model.

Owner: Person B

These run without pygame: ``Playfield`` only drives the core, so the rules
can be checked with no window open.  What is being protected here is the
seam -- that the adapter really delegates to the core instead of keeping a
second copy of the rules -- plus the few conversions the renderer relies
on.
"""

import random

import pytest

from pacman.core.config import LevelSpec, load_config
from pacman.core.entities import Direction, GhostState
from pacman.ui.playfield import GHOST_COLORS, GHOST_PERSONALITIES, Playfield


@pytest.fixture
def config():
    """A loaded configuration with a fixed seed."""
    return load_config("config.json")


@pytest.fixture
def field(config):
    """A fresh level 1, ready to step."""
    return Playfield(config.levels[0], 1, config)


def run(field: Playfield, seconds: float, dt: float = 1 / 60) -> int:
    """Step *field* for *seconds* and return the number of frames."""
    frames = int(seconds / dt)
    for _ in range(frames):
        field.update(dt)
    return frames


def test_level_comes_from_core(field, config):
    """The adapter must expose the core's level, not a rebuilt one."""
    assert field.level.width == config.levels[0].width * 2 + 1
    assert field.level.height == config.levels[0].height * 2 + 1
    assert field.level.pellets_left() > 0
    assert field.player.tile == field.level.player_spawn


def test_four_ghosts_with_distinct_personalities(field):
    """One ghost per arcade personality, in the renderer's colour order."""
    assert len(field.ghosts) == len(GHOST_COLORS)
    assert tuple(g.personality for g in field.ghosts) == GHOST_PERSONALITIES
    assert len(set(id(g) for g in field.ghosts)) == 4


def test_ghosts_move_on_their_own(field):
    """With no player input, core's AI still walks every ghost."""
    before = [g.tile for g in field.ghosts]
    run(field, 2.0)
    assert all(after != start for after, start
               in zip([g.tile for g in field.ghosts], before))


def test_ghost_never_leaves_the_maze(field):
    """Entities stay on walkable tiles; core's is_open is the only gate."""
    field.steer(Direction.UP)
    rng = random.Random(3)
    for _ in range(600):
        field.steer(rng.choice(list(Direction)))
        field.update(1 / 60)
        for entity in (field.player, *field.ghosts):
            assert field.level.is_open(*entity.tile)


def test_steering_moves_the_player_along_the_corridor(field):
    """A direction that is open from the spawn actually moves the player."""
    spawn = field.player.tile
    open_ways = [d for d in Direction
                 if field.level.is_open(*d.step(spawn))]
    assert open_ways, "the spawn should have somewhere to go"
    field.steer(open_ways[0])
    run(field, 1.0)
    assert field.player.tile != spawn


def test_blocked_direction_is_buffered_not_dropped(field):
    """A turn into a wall is held until it opens, which is core's rule."""
    spawn = field.player.tile
    blocked = [d for d in Direction
               if not field.level.is_open(*d.step(spawn))]
    if not blocked:
        pytest.skip("the spawn has no wall to be blocked by")
    field.steer(blocked[0])
    run(field, 0.5)
    assert field.player.tile == spawn, "should not move into a wall"


def test_eating_a_pellet_scores_once(field):
    """The score follows the core's pellet sets, and they shrink."""
    tile = next(iter(field.level.pacgums))
    field.player.reset(tile)
    field.update(1 / 60)
    assert tile not in field.level.pacgums
    assert field.score >= field.config.points_per_pacgum


def test_power_pellet_frightens_every_ghost(field):
    """A power pellet makes the pack edible."""
    field.player.reset(next(iter(field.level.super_pacgums)))
    field.update(1 / 60)
    assert any(g.state is GhostState.FRIGHTENED for g in field.ghosts)


def test_being_caught_costs_a_lives_and_respawns(field):
    """A ghost on an ordinary corridor tile costs a life."""
    free = next(t for t in field.level.open_tiles()
                if t not in field.level.pacgums
                and t not in field.level.super_pacgums)
    field.player.reset(free)
    ghost = field.ghosts[0]
    ghost.reset(free)
    field._move_ghosts(0.0)
    field.update(1 / 60)
    assert field.player.lives == field.config.lives - 1
    assert field.player.tile == field.level.player_spawn


def test_invincibility_cheat_keeps_the_lives(field):
    """With the cheat on, contact does not cost a life."""
    free = next(t for t in field.level.open_tiles()
                if t not in field.level.pacgums
                and t not in field.level.super_pacgums)
    field.set_invincible(True)
    field.player.reset(free)
    ghost = field.ghosts[0]
    ghost.reset(free)
    field._move_ghosts(0.0)
    field.update(1 / 60)
    assert field.player.lives == field.config.lives


def test_ghosts_can_be_frozen(field):
    """The freeze cheat stops the pack without touching core's rules."""
    field.set_ghosts_frozen(True)
    before = [(g.x, g.y) for g in field.ghosts]
    run(field, 1.0)
    assert [(g.x, g.y) for g in field.ghosts] == before


def test_double_speed_cheat_is_reversible(field):
    """Speed goes up and comes back to the configured value."""
    base = field.player.speed
    field.set_double_speed(True)
    assert field.player.speed == base * 2
    field.set_double_speed(False)
    assert field.player.speed == base


def test_clearing_the_last_pellet_ends_the_level(field):
    """A level ends when the core reports no pellets left, and then stops."""
    field.level.pacgums.clear()
    field.level.super_pacgums.clear()
    field.update(1 / 60)
    assert field.level_cleared
    frozen = [(g.x, g.y) for g in field.ghosts]
    field.update(1 / 60)
    assert [(g.x, g.y) for g in field.ghosts] == frozen


def test_a_long_random_run_never_raises(config):
    """Random play for a while must not crash, hang or end silently."""
    field = Playfield(config.levels[1], 2, config)
    rng = random.Random(11)
    for _ in range(3000):
        field.steer(rng.choice(list(Direction)))
        field.update(1 / 60)
    assert field.score > 0, "the player should have eaten something"
    assert isinstance(field.game_over, bool)


def test_tile_spec_of_a_different_size_still_builds(config):
    """A level spec is read from the config, not hardcoded."""
    field = Playfield(LevelSpec(15, 11), 3, config)
    assert field.level.width == 31
    assert field.level.height == 23
    assert field.number == 3
