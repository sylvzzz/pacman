"""Command-line entry point: ``python3 pac-man.py config.json``.

Owner: Person B
Planned contents: parse_arguments() raising UsageError,
  main() converting every PacManError into a message on stderr and an exit code
  (2 usage, 1 error, 130 keyboard interrupt). Never a traceback.
"""

from __future__ import annotations

import sys

from pacman import ui, core
from pacman.ui.log import Logger


class UsageError(RuntimeError):
    """Raised when the command-line arguments are invalid."""


def parse_arguments(
        args: list[str] | None = None) -> tuple[str, core.GameConfig]:
    """Return (config_path, config_dict) or raise UsageError."""
    if args is None:
        args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        raise UsageError("Usage: python3 pac-man.py <config.json>")

    config_path = args[0]
    try:
        config = core.load_config(config_path)
    except Exception as exc:  # pragma: no cover
        raise UsageError(f"Invalid config file: {exc}") from exc

    return config_path, config


def check_dependencies() -> None:
    """Exit with a clean message when pygame / mazegenerator are missing."""
    missing = ui.IMPORT_ERROR
    if missing is None:
        return
    Logger.error(
        f"Missing dependency: {missing.name}. "
        "Run 'make install' to set up the environment."
    )
    sys.exit(1)


def main() -> None:
    """Run the Pac-Man game.

    Parses arguments, loads configuration, creates the UI screen and runs
    the game loop.  Every error is caught and logged; no traceback ever
    reaches the user.
    """
    check_dependencies()

    try:
        config_path, config = parse_arguments()
    except UsageError as exc:
        Logger.error(f"{exc}")
        sys.exit(2)

    try:
        screen = ui.Screen(config)
        screen.run()
    except KeyboardInterrupt:
        Logger.error("\nGame interrupted by user ...")
        sys.exit(130)


if __name__ == "__main__":
    main()
