"""Tests for pacman.core.game (Person A).

Most tests rig a hand-drawn level into a ``Game`` so every collision and
pellet is placed on purpose; a few run the real generated levels.
"""

import random

import pytest

from pacman.core.config import GameConfig
from pacman.core.entities import Direction, Ghost, GhostState, Personality
from pacman.core.game import (LEVEL_SPEED_STEP, MAX_DT, MAX_LEVEL_SPEED,
                              MODE_SCHEDULE, RELEASE_STAGGER, Game, Phase)
from pacman.core.level import Level

HALL_ROWS = (
    "###########",
    "#.........#",
    "###########",
)


def rig(config: GameConfig, rows: tuple[str, ...] = HALL_ROWS,
        player: tuple[int, int] = (1, 1),
        ghosts: tuple[tuple[int, int], ...] = (),
        pacgums: tuple[tuple[int, int], ...] = ((5, 1), (8, 1))) -> Game:
    """Return a PLAYING game on a hand-drawn level."""
    game = Game(config, random.Random(1))
    level = Level([[c == "#" for c in row] for row in rows], 1, 1)
    level.player_spawn = player
    level.ghost_spawns = list(ghosts)
    level.pacgums = set(pacgums)
    game.level = level
    game.player.reset(player)
    game.ghosts = [Ghost(g, config.ghost_speed, Personality.CHASER)
                   for g in ghosts]
    game.phase = Phase.PLAYING
    return game


def run(game: Game, seconds: float, step: float = 0.016) -> None:
    """Call update repeatedly for about *seconds*."""
    for _ in range(round(seconds / step)):
        game.update(step)


def phase_of(game: Game) -> Phase:
    """Return the phase, defeating mypy's narrowing across update calls."""
    return game.phase


@pytest.fixture
def game(small_config: GameConfig) -> Game:
    """A rigged hall game with no ghosts."""
    return rig(small_config)


# --- construction and phases --------------------------------------------

def test_new_game_state(small_config: GameConfig) -> None:
    """A fresh game has full lives, zero score and a populated level."""
    g = Game(small_config, random.Random(1))
    assert g.score == 0
    assert g.lives == 3
    assert g.level_count == 2
    assert g.level_index == 0
    assert len(g.ghosts) == 4
    assert g.level.pellets_left() > 0


def test_start_with_no_ready_time_plays(small_config: GameConfig) -> None:
    """ready_time 0 skips the freeze."""
    g = Game(small_config, random.Random(1))
    g.start()
    assert phase_of(g) is Phase.PLAYING


def test_ready_freezes_then_plays(small_config: GameConfig) -> None:
    """During READY nothing moves; afterwards play begins."""
    cfg = GameConfig(**{**small_config.__dict__, "ready_time": 0.5})
    g = Game(cfg, random.Random(1))
    g.start()
    assert phase_of(g) is Phase.READY
    g.set_direction(Direction.UP)
    g.update(0.1)
    assert g.player.target is None and phase_of(g) is Phase.READY
    run(g, 0.6)
    assert phase_of(g) is Phase.PLAYING


def test_start_resets_run(small_config: GameConfig) -> None:
    """start() after some play restores score, lives and level."""
    g = Game(small_config, random.Random(1))
    g.score = 99
    g.player.lives = 1
    g.start()
    assert (g.score, g.lives, g.level_index) == (0, 3, 0)


def test_first_level_uses_config_seed(small_config: GameConfig) -> None:
    """Level 1 is the same maze every run."""
    a = Game(small_config, random.Random(1))
    b = Game(small_config, random.Random(99))
    assert a.level.grid == b.level.grid


def test_pause_toggles_and_freezes(game: Game) -> None:
    """Paused games do not move or count time."""
    game.set_direction(Direction.RIGHT)
    game.toggle_pause()
    assert phase_of(game) is Phase.PAUSED
    before = game.time_left
    game.update(0.1)
    assert game.player.x == 1.0 and game.time_left == before
    game.toggle_pause()
    assert phase_of(game) is Phase.PLAYING


def test_pause_ignored_when_over(game: Game) -> None:
    """GAME_OVER cannot be paused."""
    game.phase = Phase.GAME_OVER
    game.toggle_pause()
    assert phase_of(game) is Phase.GAME_OVER


def test_set_direction_ignored_when_paused(game: Game) -> None:
    """Keys do nothing while paused."""
    game.toggle_pause()
    game.set_direction(Direction.RIGHT)
    assert game.player.wanted is None


# --- update, movement, dt cap ---------------------------------------------

def test_dt_is_capped(game: Game) -> None:
    """A huge dt moves at most MAX_DT worth."""
    game.set_direction(Direction.RIGHT)
    game.update(10.0)
    assert game.player.x <= 1 + game.config.player_speed * MAX_DT + 1e-6


def test_negative_dt_is_ignored(game: Game) -> None:
    """Negative dt changes nothing."""
    before = game.time_left
    game.update(-1.0)
    assert game.time_left == before


def test_timer_counts_down(game: Game) -> None:
    """Playing consumes the level timer."""
    game.update(0.1)
    assert game.time_left == pytest.approx(game.config.level_max_time - 0.1)


# --- pellets and scoring -----------------------------------------------

def test_eating_pacgum_scores(game: Game) -> None:
    """Walking over a pacgum removes it and adds points."""
    game.set_direction(Direction.RIGHT)
    run(game, 1.0)
    assert (5, 1) not in game.level.pacgums
    assert game.score >= game.config.points_per_pacgum


def test_super_pacgum_frightens_ghosts(small_config: GameConfig) -> None:
    """A power pellet scores and frightens every ghost."""
    g = rig(small_config, ghosts=((9, 1),), pacgums=((8, 1),))
    g.level.super_pacgums = {(3, 1)}
    g.set_direction(Direction.RIGHT)
    run(g, 0.6)
    assert g.score >= small_config.points_per_super_pacgum
    assert g.ghosts[0].state in (GhostState.FRIGHTENED, GhostState.EATEN)


def test_score_never_decreases(small_config: GameConfig) -> None:
    """Across a long run with deaths, score is monotonic."""
    g = Game(small_config, random.Random(4))
    g.start()
    last = 0
    for i in range(600):
        g.set_direction(list(Direction)[i // 15 % 4])
        g.update(0.016)
        assert g.score >= last
        last = g.score


# --- ghosts and lives ---------------------------------------------------

def test_normal_ghost_costs_a_life_and_respawns(
        small_config: GameConfig) -> None:
    """Touching a normal ghost takes a life and resets positions."""
    g = rig(small_config, ghosts=((9, 1),))
    g.ghosts[0].tile = (1, 1)
    g.update(0.016)
    assert g.lives == 2
    assert g.player.tile == (1, 1)
    assert g.ghosts[0].tile == (9, 1)
    assert phase_of(g) is Phase.PLAYING


def test_death_keeps_pellets_and_timer(small_config: GameConfig) -> None:
    """Dying does not refill the board or the timer."""
    g = rig(small_config, ghosts=((9, 1),))
    g.ghosts[0].tile = (1, 1)
    g.update(0.016)
    assert (5, 1) in g.level.pacgums
    assert g.time_left < small_config.level_max_time


def test_edible_ghost_is_eaten(small_config: GameConfig) -> None:
    """An edible ghost gives points and goes home as EATEN."""
    g = rig(small_config, ghosts=((9, 1),))
    g.ghosts[0].tile = (1, 1)
    g.ghosts[0].frighten(4.0)
    g.update(0.016)
    assert g.lives == 3
    assert g.score == small_config.points_per_ghost
    assert g.ghosts[0].state is GhostState.EATEN


def test_eaten_ghost_is_harmless(small_config: GameConfig) -> None:
    """EATEN ghosts do not hurt even when overlapping."""
    g = rig(small_config, ghosts=((1, 1),))
    g.ghosts[0].state = GhostState.EATEN
    g.ghosts[0].respawn_timer = 5.0
    g.update(0.016)
    assert g.lives == 3


def test_game_over_at_zero_lives(small_config: GameConfig) -> None:
    """Losing the last life ends the game with lives at 0."""
    g = rig(small_config, ghosts=((9, 1),))
    g.ghosts[0].tile = (1, 1)
    g.player.lives = 1
    g.update(0.016)
    assert phase_of(g) is Phase.GAME_OVER
    assert g.lives == 0
    score = g.score
    g.update(0.1)
    assert g.score == score


def test_life_loss_enters_ready_when_configured(
        small_config: GameConfig) -> None:
    """With a ready_time, respawn freezes in READY."""
    cfg = GameConfig(**{**small_config.__dict__, "ready_time": 1.0})
    g = rig(cfg, ghosts=((9, 1),))
    g.ghosts[0].tile = (1, 1)
    g.update(0.016)
    assert phase_of(g) is Phase.READY


def test_timeout_costs_life_and_restarts_timer(game: Game) -> None:
    """Running out of time loses a life and refills the timer."""
    game.time_left = 0.01
    game.update(0.05)
    assert game.lives == 2
    assert game.time_left == game.config.level_max_time
    assert phase_of(game) is Phase.PLAYING


def test_ghosts_move_toward_player(small_config: GameConfig) -> None:
    """A chasing ghost closes the distance."""
    g = rig(small_config, ghosts=((9, 1),))
    g.cheats.invincible = True
    run(g, 0.5)
    assert g.ghosts[0].x < 9.0


# --- levels and victory -------------------------------------------------

def test_clearing_pellets_wins_level_then_advances(
        small_config: GameConfig) -> None:
    """Last pellet -> LEVEL_WON -> next level, keeping score and lives."""
    g = rig(small_config, ghosts=((9, 1),), pacgums=((3, 1),))
    g.player.lives = 2
    g.set_direction(Direction.RIGHT)
    run(g, 0.6)
    assert phase_of(g) is Phase.LEVEL_WON
    score = g.score
    run(g, 2.0)
    assert g.level_index == 1
    assert g.level.number == 2
    assert g.score == score
    assert g.lives == 2
    assert phase_of(g) is Phase.PLAYING


def test_last_level_gives_victory(small_config: GameConfig) -> None:
    """Winning the final level is VICTORY, not another level."""
    g = rig(small_config, ghosts=((9, 1),), pacgums=((3, 1),))
    g.level_index = g.level_count - 1
    g.set_direction(Direction.RIGHT)
    run(g, 0.6)
    assert phase_of(g) is Phase.VICTORY


def test_full_run_through_all_levels(small_config: GameConfig) -> None:
    """Skipping through every level ends in VICTORY."""
    g = Game(small_config, random.Random(5))
    g.start()
    g.toggle_cheats()
    for _ in range(g.level_count):
        g.skip_level()
        run(g, 2.0)
    assert phase_of(g) is Phase.VICTORY


# --- cheats -------------------------------------------------------------

def test_cheats_do_nothing_until_enabled(game: Game) -> None:
    """Without the master switch every cheat is a no-op."""
    game.toggle_invincible()
    game.add_life()
    game.add_time()
    game.skip_level()
    assert not game.cheats.invincible
    assert game.lives == 3
    assert phase_of(game) is Phase.PLAYING


def test_cheats_disabled_by_config(small_config: GameConfig) -> None:
    """cheats_enabled False blocks the master switch."""
    cfg = GameConfig(**{**small_config.__dict__, "cheats_enabled": False})
    g = Game(cfg, random.Random(1))
    g.toggle_cheats()
    assert not g.cheats.active


def test_toggle_off_clears_switches(game: Game) -> None:
    """Turning cheats off resets the individual switches."""
    game.toggle_cheats()
    game.toggle_invincible()
    game.toggle_freeze_ghosts()
    game.toggle_fast_player()
    assert game.cheats.invincible and game.cheats.freeze_ghosts
    game.toggle_cheats()
    assert not (game.cheats.active or game.cheats.invincible
                or game.cheats.freeze_ghosts or game.cheats.fast_player)


def test_invincible_ignores_ghosts(small_config: GameConfig) -> None:
    """With F1 a touching ghost costs nothing."""
    g = rig(small_config, ghosts=((9, 1),))
    g.ghosts[0].tile = (1, 1)
    g.toggle_cheats()
    g.toggle_invincible()
    g.update(0.016)
    assert g.lives == 3


def test_freeze_stops_ghosts(small_config: GameConfig) -> None:
    """Frozen ghosts stay on their tile."""
    game = rig(small_config, ghosts=((9, 1),))
    game.toggle_cheats()
    game.toggle_freeze_ghosts()
    game.toggle_invincible()
    run(game, 0.5)
    assert game.ghosts[0].x == 9.0


def test_fast_player_is_faster(small_config: GameConfig) -> None:
    """The speed cheat covers more ground in the same time."""
    slow = rig(small_config, ghosts=((9, 1),), pacgums=((9, 1),))
    fast = rig(small_config, ghosts=((9, 1),), pacgums=((9, 1),))
    fast.toggle_cheats()
    fast.toggle_fast_player()
    for g in (slow, fast):
        g.cheats.invincible = True
        g.set_direction(Direction.RIGHT)
        g.update(0.1)
    assert fast.player.x > slow.player.x


def test_add_life_and_time(game: Game) -> None:
    """F4 and F7 add a life and seconds."""
    game.toggle_cheats()
    game.add_life()
    before = game.time_left
    game.add_time()
    assert game.lives == 4
    assert game.time_left > before


def test_frighten_cheat(small_config: GameConfig) -> None:
    """F6 makes every ghost edible."""
    game = rig(small_config, ghosts=((9, 1),))
    game.toggle_cheats()
    game.frighten_ghosts()
    assert all(g.is_edible for g in game.ghosts)


def test_skip_level_wins(game: Game) -> None:
    """F5 wins the current level at once."""
    game.toggle_cheats()
    game.skip_level()
    assert phase_of(game) is Phase.LEVEL_WON


# --- pacing: release, scatter/chase, level speed ------------------------

def test_ghosts_leave_home_one_after_another(
        small_config: GameConfig) -> None:
    """Each ghost waits RELEASE_STAGGER longer than the one before."""
    g = Game(small_config, random.Random(1))
    delays = [ghost.release_timer for ghost in g.ghosts]
    assert delays == [i * RELEASE_STAGGER for i in range(4)]


def test_waiting_ghost_stays_on_its_tile(game: Game) -> None:
    """Until its timer ends a ghost does not move."""
    game.ghosts = [Ghost((9, 1), game.config.ghost_speed,
                         Personality.CHASER)]
    game.ghosts[0].release_timer = 1.0
    run(game, 0.5)
    assert game.ghosts[0].tile == (9, 1)
    assert game.ghosts[0].target is None


def test_scatter_then_chase_schedule(game: Game) -> None:
    """The first phase is scatter; chase follows; the last one is chase."""
    game.mode_time = 0.0
    assert game.scattering
    game.mode_time = MODE_SCHEDULE[0][0] + 1.0
    assert not game.scattering
    game.mode_time = sum(a + b for a, b in MODE_SCHEDULE) + 100.0
    assert not game.scattering


def test_ghosts_get_faster_each_level(small_config: GameConfig) -> None:
    """Level 2 ghosts are quicker than level 1, but never past the cap."""
    g = Game(small_config, random.Random(1))
    first = g.ghost_speed
    g._load_level(1, 3)
    assert g.ghost_speed == pytest.approx(
        small_config.ghost_speed * (1 + LEVEL_SPEED_STEP))
    assert g.ghost_speed > first
    assert g.ghost_speed <= small_config.ghost_speed * MAX_LEVEL_SPEED
