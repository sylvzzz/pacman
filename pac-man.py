"""Command-line entry point: ``python3 pac-man.py config.json``.

Owner: Person B
Planned contents: imports pacman.ui.app; parse_arguments() raising UsageError,
  main() converting every PacManError into a message on stderr and an exit code
  (2 usage, 1 error, 130 keyboard interrupt). Never a traceback.
"""

from pacman import ui, core

def main() -> None:
    import pygame

    pygame.init()
    display_info = pygame.display.Info()

    adapteted_x, adaptated_y = display_info.current_h // 2, display_info.current_h // 2

    game = core.load_config("config.json")
    screen = ui.Screen(adapteted_x, adaptated_y, 
                       game.seed, game.levels, game.points_per_pacgum, game.points_per_super_pacgum)
    screen.run()
    


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        ui.Logger.error("\nGame interruped by user ...")