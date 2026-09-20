"""Command-line entry point: ``python3 pac-man.py config.json``.

Owner: Person B
Planned contents: imports pacman.ui.app; parse_arguments() raising UsageError, main() converting
every PacManError into a message on stderr and an exit code
(2 usage, 1 error, 130 keyboard interrupt). Never a traceback.
"""

from pacman import ui

def main() -> None:

    screen = ui.Screen(1200, 720)
    screen.run()
    


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        ui.Logger.error("\nGame interruped by user ...")