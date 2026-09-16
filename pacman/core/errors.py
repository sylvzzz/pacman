"""Exception types raised by the Pac-Man package.

Owner: Person A
PacManError is the base of every error shown to the user; pac-man.py
maps each subclass to an exit code (2 for usage, 1 for the others).
"""


class PacManError(Exception):
    """Base class for every error shown to the user."""


class UsageError(PacManError):
    """Raised when the command line arguments are wrong."""


class ConfigError(PacManError):
    """Raised when the config file cannot be read or parsed."""


class MazeGenerationError(PacManError):
    """Raised when the maze package fails or returns an invalid maze."""


class HighscoreError(PacManError):
    """Raised when the highscore file cannot be read or written."""
