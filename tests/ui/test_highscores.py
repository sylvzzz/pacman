"""Tests for pacman.ui.highscores.

Owner: Person B

These run against real temporary files rather than mocks: the bugs that
matter are the round trip through JSON and a crash mid-write.
"""

import json
from pathlib import Path

import pytest

from pacman.core.errors import HighscoreError
from pacman.ui.highscores import (MAX_ENTRIES, HighscoreEntry,
                                  HighscoreTable, is_valid_name,
                                  is_valid_score, sanitize_name)


@pytest.fixture
def table(tmp_path: Path) -> HighscoreTable:
    """An empty table bound to a file in a temporary directory."""
    return HighscoreTable(str(tmp_path / "scores.json"))


def test_sanitize_keeps_letters_digits_and_spaces() -> None:
    """Anything else is dropped, and the name is cut at ten characters."""
    assert sanitize_name("a-b_c!d e1") == "abcd e1"
    assert sanitize_name("abcdefghijklmnop") == "abcdefghij"
    assert sanitize_name("  ") == ""


def test_name_and_score_validation() -> None:
    """Names are 1..10 safe characters; scores are non-negative ints."""
    assert is_valid_name("ana 2")
    assert not is_valid_name("")
    assert not is_valid_name("a" * 11)
    assert not is_valid_name("ana!")
    assert is_valid_score(0) and is_valid_score(300)
    assert not is_valid_score(-1)
    assert not is_valid_score(True)
    assert not is_valid_score("5")


def test_missing_file_is_an_empty_table(table: HighscoreTable) -> None:
    """A first run has no file; that is not an error."""
    table.load()
    assert table.entries == []


@pytest.mark.parametrize("content", ["", "{not json", "{}", "42", '"x"'])
def test_corrupt_file_is_an_empty_table(
        table: HighscoreTable, content: str) -> None:
    """Bad JSON or the wrong shape never stops the game."""
    table.path.write_text(content)
    table.load()
    assert table.entries == []


def test_bad_rows_are_skipped(table: HighscoreTable) -> None:
    """Valid rows survive next to rows with a bad name or score."""
    table.path.write_text(json.dumps([
        {"name": "ana", "score": 10},
        {"name": "bad!", "score": 10},
        {"name": "bob", "score": -4},
        {"name": "cy", "score": "9"},
        "junk",
        {"name": "dee", "score": 30},
    ]))
    table.load()
    assert table.entries == [HighscoreEntry("dee", 30),
                             HighscoreEntry("ana", 10)]


def test_add_sorts_best_first(table: HighscoreTable) -> None:
    """The table is always ordered from the highest score down."""
    for name, score in (("a", 10), ("b", 30), ("c", 20)):
        assert table.add(name, score)
    assert [e.score for e in table.entries] == [30, 20, 10]


def test_table_keeps_only_the_top_ten(table: HighscoreTable) -> None:
    """The eleventh score pushes the lowest out; a worse one is refused."""
    for i in range(MAX_ENTRIES):
        table.add(f"p{i}", (i + 1) * 100)
    assert not table.add("low", 50)
    assert table.add("top", 5000)
    assert len(table.entries) == MAX_ENTRIES
    assert table.entries[0].name == "top"
    assert all(e.score > 100 for e in table.entries)


def test_add_rejects_an_empty_name_or_bad_score(
        table: HighscoreTable) -> None:
    """Nothing invalid reaches the file."""
    assert not table.add("!!!", 10)
    assert not table.add("ana", -1)
    assert table.entries == []


def test_returning_player_keeps_only_their_best(
        table: HighscoreTable) -> None:
    """A worse run is refused; a better one replaces the old row."""
    assert table.add("ana", 100)
    assert not table.add("ana", 50)
    assert table.entries == [HighscoreEntry("ana", 100)]
    assert table.add("ana", 150)
    assert table.entries == [HighscoreEntry("ana", 150)]


def test_load_collapses_duplicate_names(table: HighscoreTable) -> None:
    """A legacy file with repeats keeps each name's highest score."""
    table.path.write_text(json.dumps([
        {"name": "gab", "score": 40},
        {"name": "gab", "score": 90},
        {"name": "gab", "score": 0},
        {"name": "cy", "score": 10},
    ]))
    table.load()
    assert table.entries == [HighscoreEntry("gab", 90),
                             HighscoreEntry("cy", 10)]


def test_save_and_load_round_trip(table: HighscoreTable) -> None:
    """What is saved is what comes back."""
    table.add("ana", 120)
    table.add("bob", 80)
    table.save()
    again = HighscoreTable(str(table.path))
    again.load()
    assert again.entries == table.entries


def test_save_leaves_no_temporary_file(
        table: HighscoreTable, tmp_path: Path) -> None:
    """The temp file is renamed over the target, not left behind."""
    table.add("ana", 1)
    table.save()
    assert [p.name for p in tmp_path.iterdir()] == ["scores.json"]


def test_save_failure_is_a_highscore_error(tmp_path: Path) -> None:
    """An unwritable location raises the project's own error."""
    table = HighscoreTable(str(tmp_path / "missing" / "scores.json"))
    table.add("ana", 1)
    with pytest.raises(HighscoreError):
        table.save()


def test_qualifies(table: HighscoreTable) -> None:
    """Any score fits an empty table; a full one needs to beat the last."""
    assert table.qualifies(0)
    for i in range(MAX_ENTRIES):
        table.add(f"p{i}", 100 + i)
    assert not table.qualifies(100)
    assert table.qualifies(101)
