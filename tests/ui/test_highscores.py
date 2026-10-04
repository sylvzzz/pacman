"""Tests for the highscore store behind pacman.ui.renderer's Screen.

Owner: Person B

``save_player`` is the only thing standing between a finished run and a
leaderboard, and it is pure file I/O over a dict, so it is worth pinning
down: a regression here is silent -- the game looks fine and the scores
just quietly stop moving.  These run against a real temp file rather than
a mock, because the bug that matters is the round trip through JSON.
"""

import json
import os
from pathlib import Path

import pytest

from pacman import core
from pacman.ui.renderer import Screen

# Resolved before the fixture chdir's into a temp directory: the tests move
# the working directory to give save_player a throwaway leaderboard.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
CONFIG = core.load_config(os.path.join(REPO, "config.json"))


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Screen:
    """A Screen plus an empty players.json in a throwaway cwd."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "players.json").write_text("{}")
    return Screen(CONFIG)


def read(path: Path) -> dict:
    """Return the parsed leaderboard."""
    return json.loads(path.read_text())


def test_first_run_creates_the_entry(tmp_path: Path, store: Screen) -> None:
    """A name that has never played starts a record at the score given."""
    store.save_player("ana", 120)
    assert read(tmp_path / "players.json") == {"ana": {"score": 120}}


def test_second_run_adds_to_the_record(tmp_path: Path, store: Screen) -> None:
    """Scores accumulate across runs rather than being overwritten.

    This is the whole point of the store, and it is what a plain
    ``players[name] = {...}`` would quietly break.
    """
    store.save_player("ana", 120)
    store.save_player("ana", 80)
    assert read(tmp_path / "players.json") == {"ana": {"score": 200}}


def test_other_players_are_untouched(tmp_path: Path, store: Screen) -> None:
    """Saving one player must not drop anybody else from the board."""
    store.save_player("ana", 120)
    store.save_player("bruno", 300)
    store.save_player("ana", 30)
    assert read(tmp_path / "players.json") == {
        "ana": {"score": 150}, "bruno": {"score": 300}}


def test_a_zero_score_run_is_still_recorded(
        tmp_path: Path, store: Screen) -> None:
    """Dying on the first pellet should not silently skip the leaderboard."""
    store.save_player("ana", 0)
    assert read(tmp_path / "players.json") == {"ana": {"score": 0}}


def test_existing_entries_survive_a_bad_shape(
        tmp_path: Path, store: Screen) -> None:
    """A hand-edited file with extra keys still loads and keeps them."""
    path = tmp_path / "players.json"
    path.write_text(json.dumps({"ana": {"score": 10, "lives": 3}}))
    store.save_player("bruno", 5)
    stored = read(path)
    assert stored["bruno"] == {"score": 5}
    assert stored["ana"]["lives"] == 3


def test_the_board_is_ranked_by_score(tmp_path: Path, store: Screen) -> None:
    """Ranking is what show_highscores displays, so check the ordering."""
    store.save_player("ana", 120)
    store.save_player("bruno", 900)
    store.save_player("carla", 45)
    players = read(tmp_path / "players.json")
    ranked = sorted(players.items(), key=lambda i: i[1]["score"],
                    reverse=True)
    assert [name for name, _ in ranked] == ["bruno", "ana", "carla"]


def drawn_lines(screen_obj: Screen,
                monkeypatch: pytest.MonkeyPatch) -> list:
    """Run show_highscores, capturing every line it would have drawn.

    Capturing the text is the only way to check the *ranking*: the pixels
    say nothing about which score is on which row.
    """
    import pygame

    drawn: list = []
    monkeypatch.setattr(
        screen_obj, "draw_line",
        lambda s, text, y, size, color, palette=None: drawn.append(text))
    screen_obj.show_highscores(pygame.Surface((screen_obj.width,
                                              screen_obj.height)))
    return drawn


def test_board_shows_the_ten_highest_not_the_first_ten(
        tmp_path: Path, store: Screen,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Rank by score, then cap.  The reverse order is the trap.

    This file lists the worst player first on purpose: taking the first
    ten keys instead of the ten highest scores renders a leaderboard that
    looks plausible and is entirely wrong.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "players.json").write_text(json.dumps(
        {f"p{i:02d}": {"score": i * 100} for i in range(15)}))

    lines = drawn_lines(store, monkeypatch)

    assert lines[0] == "Top 10 Highest Scores"
    assert len(lines) == 11, "expected a title and exactly ten rows"
    assert lines[1] == "1  -  p14  -  1400"
    assert lines[10] == "10  -  p05  -  500"


def test_an_empty_board_draws_just_the_title(
        tmp_path: Path, store: Screen,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Nobody has played yet: that is a title, not a crash."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "players.json").write_text("{}")
    assert drawn_lines(store, monkeypatch) == ["Top 10 Highest Scores"]
