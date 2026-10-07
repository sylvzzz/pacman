"""Screens of the game: each one turns keys into actions and draws itself.

Owner: Person B
Contents: Scene, MenuScene, HighscoresScene, InstructionsScene, PlayScene,
  EndScene.

``App`` owns the window and the loop; a scene only answers three questions:
what to do with a key (``handle_key``), what changes with time
(``update``) and how to draw (``draw``).  Scenes never touch pygame: keys
arrive as short names ("up", "enter", "a"...) and every drawing call goes
through ``Screen``, so this module can be tested without a window.

A scene redraws only when ``dirty`` is set (menus change on a key press,
not every frame); the play scene is always dirty.
"""

from typing import TYPE_CHECKING, Any

from pacman.core.game import Phase
from pacman.ui.highscores import MAX_NAME_LENGTH, is_valid_name
from pacman.ui.renderer import CHEAT_MENU_KEY

if TYPE_CHECKING:
    from pacman.ui.app import App

# Keys that mean "go back" on the read-only pages.
BACK_KEYS = ("left", "escape", "space", "enter")


class Scene:
    """Base class: a screen with keys, time and drawing."""

    def __init__(self, app: "App") -> None:
        """Remember the app; the first frame is always drawn."""
        self.app = app
        self.dirty = True

    def handle_key(self, key: str) -> None:
        """React to one key press; *key* is a name such as "up"."""

    def update(self, dt: float) -> None:
        """Advance time-driven state by *dt* seconds."""

    def draw(self, surface: Any) -> None:
        """Paint the whole screen onto *surface*."""


class MenuScene(Scene):
    """The main menu: Play, View Highscores, Instructions, Exit."""

    def __init__(self, app: "App") -> None:
        """Start with the first option selected."""
        super().__init__(app)
        self.selected = 0

    def handle_key(self, key: str) -> None:
        """Move the cursor, activate an option, or quit with q."""
        options = self.app.view.menu_options
        if key == "down":
            self.selected = (self.selected + 1) % len(options)
        elif key == "up":
            self.selected = (self.selected - 1) % len(options)
        elif key == "q":
            self.app.running = False
        elif key == "enter":
            self._activate(options[self.selected])
        self.dirty = True

    def _activate(self, option: str) -> None:
        """Run the chosen menu entry."""
        if option == "Play":
            self.app.set_scene(PlayScene(self.app))
        elif option == "View Highscores":
            self.app.set_scene(HighscoresScene(self.app))
        elif option == "Instructions":
            self.app.set_scene(InstructionsScene(self.app))
        elif option == "Exit":
            self.app.running = False

    def draw(self, surface: Any) -> None:
        """Draw the menu over a cleared window."""
        self.app.view.clear(surface)
        self.app.view.show_menu(surface, self.selected)


class HighscoresScene(Scene):
    """The top-10 table."""

    def handle_key(self, key: str) -> None:
        """Any back key returns to the menu."""
        if key in BACK_KEYS:
            self.app.set_scene(MenuScene(self.app))

    def draw(self, surface: Any) -> None:
        """Draw the table as the app has it loaded."""
        self.app.view.clear(surface)
        self.app.view.show_highscores(surface, self.app.table.entries)


class InstructionsScene(Scene):
    """The how-to-play page."""

    def handle_key(self, key: str) -> None:
        """Any back key returns to the menu."""
        if key in BACK_KEYS:
            self.app.set_scene(MenuScene(self.app))

    def draw(self, surface: Any) -> None:
        """Draw the instructions text."""
        self.app.view.clear(surface)
        self.app.view.show_instructions(surface)


class PlayScene(Scene):
    """A run in progress, with its pause menu and the cheat menu."""

    def __init__(self, app: "App") -> None:
        """Start a fresh run."""
        super().__init__(app)
        self.paused = False
        self.cheat_menu = False
        self.pause_index = 0
        self.cheat_index = 0
        entries = app.table.entries
        app.view.high_score = entries[0].score if entries else 0
        app.view.start_game()

    def handle_key(self, key: str) -> None:
        """Route the key to the open menu, or to the game."""
        if self.cheat_menu:
            self._cheat_menu_key(key)
        elif self.paused:
            self._pause_key(key)
        else:
            self._game_key(key)
        self.dirty = True

    def _game_key(self, key: str) -> None:
        """Keys while playing: steering, pause, cheats, restart."""
        view = self.app.view
        key = key.lower()
        if key == "escape":
            self.paused = True
            self.pause_index = 0
        elif key == "q":
            self.app.running = False
        elif key == "r":
            view.restart_game()
        elif key == CHEAT_MENU_KEY:
            self.cheat_menu = True
            self.cheat_index = 0
        elif view.cheat_key(key) is not None:
            pass                        # an armed cheat key fired
        elif view.steer(key):
            pass

    def _pause_key(self, key: str) -> None:
        """Keys in the pause menu: Resume / Main Menu."""
        if key in ("up", "down"):
            self.pause_index = 1 - self.pause_index
        elif key == "escape":
            self.paused = False
        elif key == "enter":
            if self.pause_index == 0:
                self.paused = False
            else:
                self.app.set_scene(MenuScene(self.app))

    def _cheat_menu_key(self, key: str) -> None:
        """Keys in the cheat menu: move the highlight, run, or leave.

        The arrows move the highlight; enter runs the row it is on, and
        a cheat's own key runs it from anywhere in the list.
        """
        view = self.app.view
        key = key.lower()
        count = len(view.cheat_options)
        if key in (CHEAT_MENU_KEY, "escape", "q"):
            self.cheat_menu = False
        elif key in ("up", "down"):
            step = 1 if key == "down" else -1
            self.cheat_index = (self.cheat_index + step) % count
        elif key == "enter":
            view.toggle_cheat(self.cheat_index)
        else:
            row = view.cheat_key(key)
            if row is not None:
                self.cheat_index = row

    def update(self, dt: float) -> None:
        """Step the game unless a menu is open; move on when it ends."""
        if self.paused or self.cheat_menu:
            return
        view = self.app.view
        view.step_game(dt)
        game = view.game
        if (game is not None and view.death_left <= 0
                and game.phase in (Phase.GAME_OVER, Phase.VICTORY)):
            self.app.set_scene(EndScene(
                self.app, game.phase is Phase.VICTORY, game.score))

    def draw(self, surface: Any) -> None:
        """Draw the board, or the open menu over a cleared window."""
        view = self.app.view
        if self.cheat_menu:
            view.clear(surface)
            view.cheat_menu(surface, self.cheat_index)
        elif self.paused:
            view.clear(surface)
            view.pause_menu(surface, self.pause_index)
        else:
            view.draw_frame(surface)
            self.dirty = True


class EndScene(Scene):
    """GAME OVER or the victory screen: final score and name entry.

    The player types a name and presses enter to save the score; escape
    skips saving.  Either way the game goes back to the main menu.
    """

    def __init__(self, app: "App", victory: bool, score: int) -> None:
        """Remember how the run ended and start with an empty name."""
        super().__init__(app)
        self.victory = victory
        self.score = score
        self.name = ""

    def handle_key(self, key: str) -> None:
        """Edit the name; enter saves it (when valid), escape skips."""
        if key == "escape":
            self.app.set_scene(MenuScene(self.app))
        elif key == "enter":
            name = self.name.strip()
            if is_valid_name(name):
                self.app.record_score(name, self.score)
                self.app.set_scene(MenuScene(self.app))
        elif key == "backspace":
            self.name = self.name[:-1]
        elif len(self.name) < MAX_NAME_LENGTH:
            if key == "space":
                self.name += " "
            elif len(key) == 1 and key.isalnum():
                self.name += key
        self.dirty = True

    def draw(self, surface: Any) -> None:
        """Draw the verdict, the score and the name prompt."""
        view = self.app.view
        view.clear(surface)
        view.end_screen(surface, self.victory, self.score, self.name)
