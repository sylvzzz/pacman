"""Shared pytest fixtures for tests/core and tests/ui.

Owner: Person A (but tests/ui may use these too -- see WORK_SPLIT.md).
"""

import logging
from collections.abc import Iterator

import pytest

from pacman.core.config import GameConfig, LevelSpec
from pacman.core.log import get_logger


class RecordingHandler(logging.Handler):
    """Logging handler that keeps every record instead of printing it.

    pytest's own ``caplog`` fixture attaches itself to the *root* logger
    and relies on propagation.  ``get_logger`` sets ``propagate = False``
    on purpose, so caplog would see nothing.  Attaching our own handler
    to the pacman logger works either way and does not depend on how the
    logger is configured.
    """

    def __init__(self) -> None:
        """Start with an empty record list."""
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Keep *record* in memory instead of writing it out."""
        self.records.append(record)

    def messages(self, level: int) -> list[str]:
        """Return the messages logged at exactly *level*."""
        return [record.getMessage() for record in self.records
                if record.levelno == level]

    @property
    def warnings(self) -> list[str]:
        """Return the WARNING messages logged so far."""
        return self.messages(logging.WARNING)

    @property
    def infos(self) -> list[str]:
        """Return the INFO messages logged so far."""
        return self.messages(logging.INFO)


@pytest.fixture
def log_records() -> Iterator[RecordingHandler]:
    """Capture everything pacman logs during one test."""
    logger = get_logger()
    handler = RecordingHandler()
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


@pytest.fixture
def small_config() -> GameConfig:
    """A tiny, fast config for headless simulations.

    Built directly rather than through ``build_config`` so it stays
    usable while build_config is still being written, and so a bug in
    the parser cannot quietly change what the game tests run against.

    ``ready_time`` is 0.0 so a test does not have to burn the READY
    freeze before the player moves.  Two levels only -- the ten-level
    minimum is a rule ``build_config`` enforces, not one ``GameConfig``
    itself imposes.
    """
    return GameConfig(
        highscore_filename="test_highscores.json",
        lives=3,
        seed=1,
        level_max_time=30.0,
        frightened_time=4.0,
        ghost_respawn_time=2.0,
        ready_time=0.0,
        player_speed=6.0,
        ghost_speed=4.0,
        pacgum_density=100,
        levels=(LevelSpec(6, 5), LevelSpec(7, 5)),
    )
