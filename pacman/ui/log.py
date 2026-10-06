"""Coloured console messages."""


class Logger:
    """Prints a message in a colour; every method is static."""

    @staticmethod
    def error(text: str) -> None:
        """Print *text* in red."""
        print("\033[31m" + text + "\033[0m")

    @staticmethod
    def success(text: str) -> None:
        """Print *text* in green."""
        print("\033[92m" + text + "\033[0m")

    @staticmethod
    def warning(text: str) -> None:
        """Print *text* in yellow."""
        print("\033[33m" + text + "\033[0m")

    @staticmethod
    def log(text: str) -> None:
        """Print *text* unchanged."""
        print(text)
