"""Tests for the seam between ``Screen`` and the core ``Game``.

Owner: Person B

The screen must hold no rules of its own: it forwards input to ``Game``
and redraws whatever level the game is on.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest  # noqa: E402

from pacman import core  # noqa: E402
from pacman.core.game import Phase  # noqa: E402
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


def test_cheat_keys_need_cheat_mode(screen_obj: Screen) -> None:
    """F1 does nothing until C turns cheat mode on."""
    assert screen_obj.game is not None
    screen_obj.cheat_key("f1")
    assert not screen_obj.game.cheats.invincible
    screen_obj.cheat_key("c")
    screen_obj.cheat_key("f1")
    assert screen_obj.game.cheats.invincible
    assert screen_obj.cheats_activated["INVINCIBILITY"]


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
