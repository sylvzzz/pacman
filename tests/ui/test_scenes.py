"""Tests for pacman.ui.scenes and App, without opening a window.

Owner: Person B

Keys are fed to the current scene by name, exactly as ``App.run`` does,
so the whole flow (menu, name, play, pause, end, highscores) is covered.
"""

import dataclasses
import os
from pathlib import Path

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from pacman import core  # noqa: E402
from pacman.core.entities import Direction  # noqa: E402
from pacman.core.game import Phase  # noqa: E402
from pacman.ui.app import App  # noqa: E402
from pacman.ui.scenes import (EndScene, HighscoresScene,  # noqa: E402
                              InstructionsScene, MenuScene, PlayScene)

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def app(tmp_path: Path) -> App:
    """An App whose highscore file lives in a temporary directory."""
    config = dataclasses.replace(
        core.load_config(str(REPO / "config.json")),
        highscore_filename=str(tmp_path / "scores.json"))
    return App(config)


def press(app: App, *keys: str) -> None:
    """Send each key name to the current scene."""
    for key in keys:
        app.scene.handle_key(key)


def start_run(app: App) -> PlayScene:
    """Choose Play in the menu and return the play scene."""
    press(app, "enter")
    assert isinstance(app.scene, PlayScene)
    return app.scene


def test_menu_selection_wraps(app: App) -> None:
    """Up from the first option lands on the last one."""
    press(app, "up")
    assert isinstance(app.scene, MenuScene)
    assert app.scene.selected == len(app.view.menu_options) - 1


def test_menu_opens_pages_and_back(app: App) -> None:
    """Highscores and Instructions open and return to the menu."""
    press(app, "down", "enter")
    assert isinstance(app.scene, HighscoresScene)
    press(app, "escape")
    press(app, "down", "down", "enter")
    assert isinstance(app.scene, InstructionsScene)
    press(app, "left")
    assert isinstance(app.scene, MenuScene)


def test_exit_option_and_q_quit(app: App) -> None:
    """Both the Exit entry and q stop the loop."""
    press(app, "q")
    assert not app.running
    app.running = True
    press(app, "up", "enter")
    assert not app.running


def test_pause_menu_resume_and_main_menu(app: App) -> None:
    """Escape pauses; Resume continues; Main Menu leaves the run."""
    play = start_run(app)
    press(app, "escape")
    assert play.paused
    press(app, "enter")
    assert not play.paused
    press(app, "escape", "down", "enter")
    assert isinstance(app.scene, MenuScene)


def test_paused_game_does_not_advance(app: App) -> None:
    """Time stands still while the pause menu is open."""
    play = start_run(app)
    game = app.view.game
    assert game is not None
    press(app, "escape")
    before = game.time_left
    for _ in range(30):
        play.update(0.05)
    assert game.time_left == before


def test_c_opens_the_cheat_menu(app: App) -> None:
    """C opens it and closes it again; the old 4-2 sequence does not."""
    play = start_run(app)
    press(app, "4", "2")
    assert not play.cheat_menu
    press(app, "c")
    assert play.cheat_menu
    press(app, "c")
    assert not play.cheat_menu
    press(app, "c", "escape")
    assert not play.cheat_menu


def test_cheat_menu_letter_runs_its_cheat(app: App) -> None:
    """I needs its row armed by enter; then it turns on invincibility."""
    play = start_run(app)
    game = app.view.game
    assert game is not None
    press(app, "c", "i")                    # not armed: the key is dead
    assert play.cheat_menu
    assert not game.cheats.active and not game.cheats.invincible
    press(app, "down", "enter", "i")        # arm INVINCIBILITY, then I
    assert game.cheats.active and game.cheats.invincible
    assert app.view.cheats_activated["INVINCIBILITY"]
    assert play.cheat_index == 1


def test_enter_arms_the_row_but_does_not_run_it(app: App) -> None:
    """Enter only unlocks the row's key; the letter itself runs it."""
    play = start_run(app)
    game = app.view.game
    assert game is not None
    press(app, "c", "enter")                # MORE LIVES, first row
    assert game.lives == 3                  # arming adds no life
    assert app.view.cheats_activated["MORE LIVES"]
    press(app, "l")                         # armed: L runs the cheat
    assert game.lives == 4
    press(app, "l")                         # and keeps running it
    assert game.lives == 5
    press(app, "enter")                     # disarm again: L goes dead
    assert not app.view.cheats_activated["MORE LIVES"]
    press(app, "l")
    assert game.lives == 5
    assert play.cheat_index == 0


def test_cheat_menu_letters_are_case_insensitive(app: App) -> None:
    """Caps lock must not make the shortcuts go dead."""
    play = start_run(app)
    game = app.view.game
    assert game is not None
    press(app, "C", "down", "down", "enter", "S")  # arm 2x SPEED, then S
    assert play.cheat_menu and game.cheats.fast_player


def test_one_shot_cheats_mark_their_row_used(app: App) -> None:
    """The cheats with no switch in the core light up once they run."""
    start_run(app)
    game = app.view.game
    assert game is not None
    press(app, "c", "l")                    # not armed: nothing runs
    assert game.lives == 3
    assert not app.view.cheats_activated["MORE LIVES"]
    press(app, "enter", "l")                # arm, then run
    assert game.lives == 4
    assert app.view.cheats_activated["MORE LIVES"]
    assert not app.view.cheats_activated["INVINCIBILITY"]


def test_one_shot_cheats_can_be_turned_off_again(app: App) -> None:
    """Disarming clears the row; the extra life is not taken back."""
    start_run(app)
    game = app.view.game
    assert game is not None
    press(app, "c", "enter", "l")           # arm, then take the life
    assert game.lives == 4
    assert app.view.cheats_activated["MORE LIVES"]
    press(app, "enter")                     # disarm
    assert game.lives == 4
    assert not app.view.cheats_activated["MORE LIVES"]
    press(app, "l")                         # disarmed: L no longer runs
    assert game.lives == 4


def test_armed_l_adds_lives_during_play(app: App) -> None:
    """Toggle ON unlocks L for the rest of the run, menu open or not."""
    play = start_run(app)
    game = app.view.game
    assert game is not None
    press(app, "c", "enter")                # arm MORE LIVES
    press(app, "c")                         # close the menu, keep playing
    assert not play.cheat_menu
    press(app, "l")
    assert game.lives == 4
    press(app, "l")                         # stays armed: keeps stacking
    assert game.lives == 5
    press(app, "c", "enter", "c")           # disarm and play on
    press(app, "l")
    assert game.lives == 5


def finish_run(app: App, score: int, phase: Phase) -> EndScene:
    """Start a run, end it with *phase* and return the end scene."""
    play = start_run(app)
    game = app.view.game
    assert game is not None
    game.score = score
    game.phase = phase
    play.update(0.016)
    assert isinstance(app.scene, EndScene)
    return app.scene


@pytest.mark.parametrize("phase,victory", [(Phase.GAME_OVER, False),
                                           (Phase.VICTORY, True)])
def test_both_endings_ask_for_a_name(
        app: App, phase: Phase, victory: bool) -> None:
    """Winning or losing opens the end screen with the final score."""
    end = finish_run(app, 440, phase)
    assert end.victory is victory
    assert end.score == 440
    assert app.table.entries == []        # nothing saved before the name


def test_name_is_saved_and_menu_returns(app: App) -> None:
    """Typing a name and pressing enter saves it and goes to the menu."""
    finish_run(app, 440, Phase.GAME_OVER)
    press(app, "a", "n", "a", "space", "2", "enter")
    assert isinstance(app.scene, MenuScene)
    assert [(e.name, e.score) for e in app.table.entries] == [("ana 2", 440)]
    assert Path(app.table.path).exists()


def test_empty_name_is_not_accepted(app: App) -> None:
    """Enter with no name stays on the end screen."""
    finish_run(app, 10, Phase.GAME_OVER)
    press(app, "enter")
    assert isinstance(app.scene, EndScene)
    press(app, "space", "enter")
    assert isinstance(app.scene, EndScene)
    assert app.table.entries == []


def test_name_rules_on_the_end_screen(app: App) -> None:
    """Only letters, digits and spaces, at most ten characters."""
    end = finish_run(app, 10, Phase.GAME_OVER)
    press(app, "!", "-", "a")
    assert end.name == "a"
    for char in "bcdefghijklmn":
        press(app, char)
    assert end.name == "abcdefghij"
    press(app, "backspace")
    assert end.name == "abcdefghi"


def test_escape_skips_saving(app: App) -> None:
    """Escape returns to the menu without touching the table."""
    finish_run(app, 99, Phase.VICTORY)
    press(app, "x", "escape")
    assert isinstance(app.scene, MenuScene)
    assert app.table.entries == []


def test_zero_score_can_be_saved(app: App) -> None:
    """Scores are non-negative, so zero is a valid entry."""
    finish_run(app, 0, Phase.GAME_OVER)
    press(app, "z", "enter")
    assert [e.score for e in app.table.entries] == [0]


def test_leaving_through_the_pause_menu_saves_nothing(app: App) -> None:
    """Main Menu abandons the run; no name is asked, nothing is saved."""
    start_run(app)
    press(app, "escape", "down", "enter")
    assert isinstance(app.scene, MenuScene)
    assert app.table.entries == []


def test_wasd_steers_like_the_arrows(app: App) -> None:
    """The WASD keys buffer turns in the core."""
    start_run(app)
    game = app.view.game
    assert game is not None
    press(app, "a")
    assert game.player.wanted is Direction.LEFT
    press(app, "d")
    assert game.player.wanted is Direction.RIGHT


def test_arrow_keys_steer_and_r_restarts(app: App) -> None:
    """Arrows buffer a turn in the core; r starts the run over."""
    start_run(app)
    game = app.view.game
    assert game is not None
    press(app, "left")
    assert game.player.wanted is not None
    game.score = 50
    press(app, "r")
    assert app.view.game is not None and app.view.game.score == 0
