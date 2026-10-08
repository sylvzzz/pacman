"""Persistent top-10 highscore table stored as JSON.

Owner: Person B
Contents: HighscoreEntry, sanitize_name(), is_valid_name(),
  is_valid_score(), HighscoreTable.

The file is a JSON list of ``{"name": str, "score": int}`` objects, best
first, one row per name — a player's best run only.  Loading never fails
the game: a missing, unreadable or corrupt file is an empty table, and bad
rows inside a good file are skipped.
Saving writes a temporary file next to the target and renames it over
the old one, so a crash mid-write cannot leave half a table behind.
"""

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pacman.core.errors import HighscoreError

MAX_NAME_LENGTH = 10
MAX_ENTRIES = 10


@dataclass(frozen=True)
class HighscoreEntry:
    """One saved score.

    Attributes:
        name: who scored, already valid per ``is_valid_name``.
        score: points, a non-negative integer.
    """

    name: str
    score: int


def sanitize_name(raw: str) -> str:
    """Keep only letters, digits and spaces, at most 10 characters.

    Args:
        raw: text typed by the player.

    Returns:
        A valid name; empty when nothing usable was typed.
    """
    kept = "".join(ch for ch in raw if ch.isascii() and (ch.isalnum()
                                                         or ch == " "))
    return kept[:MAX_NAME_LENGTH].strip()


def is_valid_name(name: str) -> bool:
    """Return True when *name* follows the highscore naming rules."""
    return 0 < len(name) <= MAX_NAME_LENGTH and sanitize_name(name) == name


def is_valid_score(score: Any) -> bool:
    """Return True for a non-negative integer (booleans excluded)."""
    return (isinstance(score, int) and not isinstance(score, bool)
            and score >= 0)


class HighscoreTable:
    """The top-10 table: loaded tolerantly, saved atomically."""

    def __init__(self, path: str) -> None:
        """Bind the table to *path* without touching the disk."""
        self.path = Path(path)
        self.entries: list[HighscoreEntry] = []

    def load(self) -> None:
        """Read the file into ``entries``, tolerating any problem.

        A missing file, bad JSON or the wrong shape give an empty table;
        rows with an invalid name or score are dropped.
        """
        self.entries = []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, list):
            return
        for row in raw:
            if not isinstance(row, dict):
                continue
            name, score = row.get("name"), row.get("score")
            if (isinstance(name, str) and is_valid_name(name)
                    and isinstance(score, int) and is_valid_score(score)):
                self.entries.append(HighscoreEntry(name, score))
        self._trim()

    def _trim(self) -> None:
        """Sort best first, one row per name (its best), then keep ten.

        The sort is stable, so ties keep age order.  Duplicates already
        in the file collapse to each name's highest score here, which
        is why loading a legacy file with repeats repairs itself on the
        next save.
        """
        self.entries.sort(key=lambda entry: entry.score, reverse=True)
        kept: list[HighscoreEntry] = []
        seen: set[str] = set()
        for entry in self.entries:
            if entry.name not in seen:
                seen.add(entry.name)
                kept.append(entry)
        self.entries = kept[:MAX_ENTRIES]

    def qualifies(self, score: int) -> bool:
        """Return True when *score* would make it into the table."""
        if not is_valid_score(score):
            return False
        return (len(self.entries) < MAX_ENTRIES
                or score > self.entries[-1].score)

    def add(self, name: str, score: int) -> bool:
        """Record a run for *name* and trim the table to ten.

        A name holds at most one row: its best run.  A returning player
        only replaces that row when the new score beats it.

        Args:
            name: the player; sanitised first.  An empty result is
                rejected.
            score: points to record.

        Returns:
            True when the score is now the player's row in the table.
        """
        clean = sanitize_name(name)
        if not clean or not is_valid_score(score):
            return False
        best = max((e.score for e in self.entries if e.name == clean),
                   default=-1)
        if score <= best:
            return False
        if not self.qualifies(score):
            return False
        self.entries.append(HighscoreEntry(clean, score))
        self._trim()
        return True

    def save(self) -> None:
        """Write the table through a temporary file and a rename.

        Raises:
            HighscoreError: the file could not be written.
        """
        data = [{"name": e.name, "score": e.score} for e in self.entries]
        directory = self.path.parent if str(self.path.parent) else Path(".")
        tmp_name = ""
        try:
            fd, tmp_name = tempfile.mkstemp(
                dir=directory, prefix=".highscores-", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
            os.replace(tmp_name, self.path)
        except OSError as exc:
            if tmp_name:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
            raise HighscoreError(
                f"cannot save highscores to {self.path}: {exc}") from exc
