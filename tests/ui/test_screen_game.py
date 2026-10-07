"""Tests for the seam between ``Screen`` and the core ``Game``.

Owner: Person B

The screen must hold no rules of its own: it forwards input to ``Game``
and redraws whatever level the game is on.
"""

import dataclasses
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest  # noqa: E402

from pacman import core  # noqa: E402
from pacman.core.game import Game, Phase  # noqa: E402
from pacman.ui.renderer import Screen  # noqa: E402


@pytest.fixture
def screen_obj() -> Screen:
    """A Screen on a fresh run of the shipped config."""
    screen = Screen(core.load_config("config.json"))
    screen.start_game()
    return screen


def test_start_game_draws_the_level_the_core_built(
        screen_obj: Screen) -> None:
    """The maze on screen comes from the seed of the core's level."""
    assert screen_obj.game is not None
    assert screen_obj._shown_level is screen_obj.game.level


def test_cheat_keys_need_their_row_armed(screen_obj: Screen) -> None:
    """A key runs nothing until enter arms its row; then only it runs."""
    assert screen_obj.game is not None
    screen_obj.cheat_key("x")
    screen_obj.cheat_key("enter")
    for key in "lisfgnt":
        screen_obj.cheat_key(key)          # no row is armed yet
    assert not screen_obj.game.cheats.active
    assert screen_obj.game.lives == 3
    screen_obj.toggle_cheat(0)             # arm MORE LIVES
    screen_obj.toggle_cheat(1)             # arm INVINCIBILITY
    screen_obj.cheat_key("s")              # not armed: still dead
    assert not screen_obj.game.cheats.fast_player
    screen_obj.cheat_key("l")              # armed: runs
    screen_obj.cheat_key("i")              # armed: runs
    assert screen_obj.game.cheats.active
    assert screen_obj.game.lives == 4
    assert screen_obj.game.cheats.invincible
    assert screen_obj.cheats_activated["MORE LIVES"]
    assert screen_obj.cheats_activated["INVINCIBILITY"]


def test_cheats_stay_dead_when_the_config_disables_them(
        screen_obj: Screen) -> None:
    """With cheats_enabled false neither arming nor running changes a thing."""
    screen_obj.config = dataclasses.replace(screen_obj.config,
                                            cheats_enabled=False)
    screen_obj.game = Game(screen_obj.config)
    assert screen_obj.game is not None
    screen_obj.toggle_cheat(0)             # arming must fail too
    screen_obj.cheat_key("i")
    screen_obj.cheat_key("l")
    assert not screen_obj.game.cheats.active
    assert not screen_obj.game.cheats.invincible
    assert not screen_obj.cheats_activated["INVINCIBILITY"]
    assert not screen_obj.cheats_activated["MORE LIVES"]


def test_scare_needs_its_row_armed(screen_obj: Screen) -> None:
    """G frightens only after enter arms the SCARE GHOSTS row."""
    game = screen_obj.game
    assert game is not None
    game.phase = Phase.PLAYING
    screen_obj.cheat_key("g")
    assert not screen_obj.cheats_activated["SCARE GHOSTS"]
    assert not any(g.is_edible for g in game.ghosts)
    screen_obj.toggle_cheat(4)             # SCARE GHOSTS is row 4
    screen_obj.cheat_key("g")
    assert screen_obj.cheats_activated["SCARE GHOSTS"]
    assert all(g.is_edible for g in game.ghosts)


def test_new_level_is_noticed_and_redrawn(screen_obj: Screen) -> None:
    """When the game moves on, ``sync_level`` follows its new maze."""
    game = screen_obj.game
    assert game is not None
    game.toggle_cheats()
    game.phase = Phase.PLAYING
    game.skip_level()
    for _ in range(100):
        game.update(0.1)
        if game.level_index == 1:
            break
    assert game.level is not screen_obj._shown_level
    screen_obj.sync_level()
    assert screen_obj._shown_level is game.level
    assert screen_obj.current_level == 1
