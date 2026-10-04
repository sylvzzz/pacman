"""Tests for pacman.core.entities (Person A).

Levels are drawn as text ('#' wall, '.' corridor) so each test shows the
maze it runs in.  Nothing here touches the maze package.
"""

import pytest

from pacman.core.entities import (
    Direction, DirectionPicker, Ghost, GhostState, Mover, Personality,
    Player,
)
from pacman.core.level import Level, Point


def make_level(*rows: str) -> Level:
    """Build a Level from text rows: '#' is a wall, anything else open."""
    return Level([[c == "#" for c in row] for row in rows], 1, 1)


# One straight corridor, tiles (1, 1), (2, 1), (3, 1).
CORRIDOR = make_level(
    "#####",
    "#...#",
    "#####",
)

# The corridor plus a branch going down from its right end, (3, 2).
BRANCH = make_level(
    "#####",
    "#...#",
    "###.#",
    "#####",
)


def always(direction: Direction | None) -> DirectionPicker:
    """Return a picker that always answers *direction*."""
    return lambda: direction


# --------------------------------------------------------------- Direction

@pytest.mark.parametrize("direction, dx, dy", [
    (Direction.UP, 0, -1),
    (Direction.DOWN, 0, 1),
    (Direction.LEFT, -1, 0),
    (Direction.RIGHT, 1, 0),
])
def test_direction_deltas(direction: Direction, dx: int, dy: int) -> None:
    """Each direction exposes its tile step; y grows downwards."""
    assert (direction.dx, direction.dy) == (dx, dy)


@pytest.mark.parametrize("direction, expected", [
    (Direction.UP, Direction.DOWN),
    (Direction.DOWN, Direction.UP),
    (Direction.LEFT, Direction.RIGHT),
    (Direction.RIGHT, Direction.LEFT),
])
def test_direction_opposite(direction: Direction,
                            expected: Direction) -> None:
    """opposite() reverses, and reversing twice gives the start back."""
    assert direction.opposite() is expected
    assert direction.opposite().opposite() is direction


def test_direction_step() -> None:
    """step() moves one tile in the direction, from any tile."""
    assert Direction.RIGHT.step((3, 4)) == (4, 4)
    assert Direction.UP.step((3, 4)) == (3, 3)
    assert Direction.LEFT.step((0, 0)) == (-1, 0)


# ------------------------------------------------------------------- Mover

def test_mover_starts_standing_on_its_tile() -> None:
    """A new mover is on its tile, stopped, with no direction yet."""
    m = Mover((1, 1), 5.0)
    assert (m.x, m.y) == (1.0, 1.0)
    assert m.target is None
    assert m.direction is None


def test_mover_position_is_interpolated() -> None:
    """Half a tile of travel puts it half a tile along, not on a tile."""
    m = Mover((1, 1), 5.0)
    m.advance(0.1, CORRIDOR, always(Direction.RIGHT))  # 0.5 tile
    assert m.x == pytest.approx(1.5)
    assert m.y == pytest.approx(1.0)
    assert m.tile == (1, 1)
    assert m.target == (2, 1)


def test_mover_arrives_on_the_next_tile() -> None:
    """A full tile of travel lands exactly on it and clears the target."""
    m = Mover((1, 1), 5.0)
    m.advance(0.2, CORRIDOR, always(Direction.RIGHT))  # 1.0 tile
    assert m.tile == (2, 1)
    assert m.target is None
    assert m.progress == 0.0
    assert (m.x, m.y) == (2.0, 1.0)


def test_mover_records_direction_and_keeps_it_when_stopped() -> None:
    """direction is the last way moved, so the sprite keeps facing it."""
    m = Mover((1, 1), 5.0)
    m.advance(0.2, CORRIDOR, always(Direction.RIGHT))
    m.advance(0.2, CORRIDOR, always(None))
    assert m.direction is Direction.RIGHT


def test_mover_stops_dead_at_a_wall() -> None:
    """Leftover distance is thrown away at a wall, never spent in it."""
    m = Mover((1, 1), 10.0)
    m.advance(0.25, CORRIDOR, always(Direction.RIGHT))  # 2.5 tiles
    assert m.tile == (3, 1)
    assert (m.x, m.y) == (3.0, 1.0)


def test_mover_huge_dt_does_not_tunnel() -> None:
    """A stalled window (huge dt) still ends inside the corridor."""
    m = Mover((1, 1), 5.0)
    m.advance(100.0, CORRIDOR, always(Direction.RIGHT))
    assert m.tile == (3, 1)
    assert m.target is None


def test_mover_refuses_to_step_into_a_wall() -> None:
    """A picker asking for a wall direction leaves the mover untouched."""
    m = Mover((1, 1), 5.0)
    m.advance(0.2, CORRIDOR, always(Direction.UP))
    assert m.tile == (1, 1)
    assert m.target is None
    assert m.direction is None


def test_mover_stands_still_when_picker_answers_none() -> None:
    """None from the picker means stay put."""
    m = Mover((1, 1), 5.0)
    m.advance(1.0, CORRIDOR, always(None))
    assert (m.x, m.y) == (1.0, 1.0)


def test_mover_zero_dt_does_not_move() -> None:
    """No time, no movement -- and the picker is not even needed."""
    m = Mover((1, 1), 5.0)
    m.advance(0.0, CORRIDOR, always(Direction.RIGHT))
    assert m.tile == (1, 1)
    assert m.target is None


def test_mover_asks_only_at_tile_centres() -> None:
    """The picker is called on a centre, never in the middle of a tile."""
    calls: list[int] = []

    def pick() -> Direction:
        calls.append(1)
        return Direction.RIGHT

    m = Mover((1, 1), 5.0)
    m.advance(0.1, CORRIDOR, pick)   # half a tile: asked once, to start
    m.advance(0.05, CORRIDOR, pick)  # still mid-tile: not asked again
    assert len(calls) == 1


def test_mover_asks_once_per_tile_crossed() -> None:
    """Two whole tiles in one call means two questions, one per centre."""
    calls: list[int] = []

    def pick() -> Direction:
        calls.append(1)
        return Direction.RIGHT

    m = Mover((1, 1), 4.0)
    m.advance(0.5, CORRIDOR, pick)  # exactly 2 tiles
    assert m.tile == (3, 1)
    assert len(calls) == 2


def test_mover_reset_teleports_and_stops() -> None:
    """reset() drops a journey in progress and the remembered heading."""
    m = Mover((1, 1), 5.0)
    m.advance(0.1, CORRIDOR, always(Direction.RIGHT))
    m.reset((3, 1))
    assert m.tile == (3, 1)
    assert m.target is None
    assert m.progress == 0.0
    assert m.direction is None
    assert (m.x, m.y) == (3.0, 1.0)
    assert m.speed == 5.0


# ------------------------------------------------------------------ Player

def test_player_keeps_lives() -> None:
    """The constructor stores the starting lives."""
    assert Player((1, 1), 5.0, 3).lives == 3


def test_player_without_input_stands_still() -> None:
    """No buffered turn and no heading means no direction."""
    p = Player((1, 1), 5.0, 3)
    assert p.pick_direction(CORRIDOR) is None


def test_player_takes_the_buffered_turn_when_open() -> None:
    """The buffered turn wins over the current heading when it is open."""
    p = Player((3, 1), 5.0, 3)
    p.direction = Direction.LEFT
    p.wanted = Direction.DOWN
    assert p.pick_direction(BRANCH) is Direction.DOWN


def test_player_keeps_going_when_the_turn_is_blocked() -> None:
    """A buffered turn into a wall is skipped, not obeyed."""
    p = Player((2, 1), 5.0, 3)
    p.direction = Direction.RIGHT
    p.wanted = Direction.DOWN  # (2, 2) is a wall
    assert p.pick_direction(BRANCH) is Direction.RIGHT


def test_player_stops_at_a_wall() -> None:
    """Heading into a wall with no usable turn gives None."""
    p = Player((3, 1), 5.0, 3)
    p.direction = Direction.RIGHT
    assert p.pick_direction(CORRIDOR) is None


def test_player_blocked_turn_stays_buffered() -> None:
    """The turn is remembered until a junction lets it through."""
    p = Player((2, 1), 5.0, 3)
    p.direction = Direction.RIGHT
    p.wanted = Direction.DOWN
    p.pick_direction(BRANCH)
    assert p.wanted is Direction.DOWN


def test_player_update_runs_along_a_corridor() -> None:
    """update() steers by pick_direction and moves like any Mover."""
    p = Player((1, 1), 5.0, 3)
    p.wanted = Direction.RIGHT
    p.update(0.4, BRANCH)  # 2 tiles
    assert p.tile == (3, 1)


def test_player_turns_at_the_next_centre_not_mid_tile() -> None:
    """A turn pressed mid-tile is taken on arrival, using leftover time."""
    p = Player((1, 1), 5.0, 3)
    p.wanted = Direction.RIGHT
    p.update(0.3, BRANCH)           # 1.5 tiles: halfway to (3, 1)
    assert p.tile == (2, 1)
    p.wanted = Direction.DOWN       # pressed mid-tile
    p.update(0.3, BRANCH)           # 0.5 to arrive, 1.0 down the branch
    assert p.tile == (3, 2)
    assert p.direction is Direction.DOWN


def test_player_reset_clears_input_and_keeps_lives() -> None:
    """Respawning forgets the buffer and the journey, not the lives."""
    p = Player((1, 1), 5.0, 2)
    p.wanted = Direction.RIGHT
    p.update(0.1, BRANCH)
    p.reset((2, 1))
    assert p.tile == (2, 1)
    assert p.wanted is None
    assert p.direction is None
    assert p.target is None
    assert p.lives == 2


# ------------------------------------------------------------------- Ghost

def make_ghost(home: Point = (1, 1)) -> Ghost:
    """Return a NORMAL ghost on *home*."""
    return Ghost(home, 4.0, Personality.CHASER)


def test_ghost_starts_normal_on_its_home() -> None:
    """A new ghost is NORMAL, at home, harmful and not edible."""
    g = make_ghost((3, 1))
    assert g.home == (3, 1)
    assert g.tile == (3, 1)
    assert g.personality is Personality.CHASER
    assert g.state is GhostState.NORMAL
    assert g.is_active
    assert not g.is_edible


def test_ghost_frighten_makes_it_edible() -> None:
    """frighten() makes a NORMAL ghost edible; it still touches the player."""
    g = make_ghost()
    g.frighten(8.0)
    assert g.state is GhostState.FRIGHTENED
    assert g.is_edible
    assert g.is_active


def test_ghost_frightened_expires_back_to_normal() -> None:
    """Edibility ends once the full duration has passed, not before."""
    g = make_ghost()
    g.frighten(2.0)
    g.tick(1.9)
    assert g.is_edible
    g.tick(0.2)
    assert g.state is GhostState.NORMAL
    assert g.frightened_timer == 0.0


def test_ghost_frighten_again_restarts_the_timer() -> None:
    """A second super-pacgum extends the effect instead of stacking."""
    g = make_ghost()
    g.frighten(2.0)
    g.tick(1.5)
    g.frighten(2.0)
    g.tick(1.5)
    assert g.is_edible
    g.tick(0.6)
    assert g.state is GhostState.NORMAL


def test_ghost_eat_sends_it_home_inactive() -> None:
    """An eaten ghost teleports home and cannot touch anyone."""
    g = make_ghost((1, 1))
    g.reset((3, 1))
    g.frighten(8.0)
    g.eat(5.0)
    assert g.tile == (1, 1)
    assert g.target is None
    assert g.state is GhostState.EATEN
    assert not g.is_active
    assert not g.is_edible


def test_ghost_respawns_after_the_delay() -> None:
    """EATEN lasts exactly respawn_time, then NORMAL and active again."""
    g = make_ghost()
    g.eat(5.0)
    g.tick(4.9)
    assert not g.is_active
    g.tick(0.2)
    assert g.state is GhostState.NORMAL
    assert g.is_active
    assert g.respawn_timer == 0.0


def test_ghost_eaten_returns_normal_not_frightened() -> None:
    """The frightened timer is forgotten when eaten."""
    g = make_ghost()
    g.frighten(8.0)
    g.eat(1.0)
    g.tick(1.5)
    assert g.state is GhostState.NORMAL
    assert g.frightened_timer == 0.0


def test_ghost_cannot_be_frightened_while_eaten() -> None:
    """A ghost already heading home is not edible a second time."""
    g = make_ghost()
    g.eat(5.0)
    g.frighten(8.0)
    assert g.state is GhostState.EATEN


def test_ghost_tick_does_nothing_when_normal() -> None:
    """Ticking a NORMAL ghost changes nothing."""
    g = make_ghost()
    g.tick(10.0)
    assert g.state is GhostState.NORMAL


def test_ghost_reset_restores_normal_and_clears_timers() -> None:
    """reset() is a full return to the start-of-level state."""
    g = make_ghost()
    g.frighten(8.0)
    g.reset((2, 1))
    assert g.tile == (2, 1)
    assert g.state is GhostState.NORMAL
    assert g.frightened_timer == 0.0
    assert g.respawn_timer == 0.0


def test_ghost_moves_like_any_mover() -> None:
    """Ghosts inherit Mover.advance: same corridors, same stopping."""
    g = make_ghost((1, 1))
    g.advance(10.0, CORRIDOR, always(Direction.RIGHT))
    assert g.tile == (3, 1)
