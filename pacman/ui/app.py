"""Application loop: window, timing, event dispatch and scene switching.

Owner: Person B
Contents: App, key_name().

``App`` is the only place besides ``renderer`` that talks to pygame.  It
turns pygame events into key names for the current ``Scene``, calls
``update`` with a delta time from ``time.perf_counter``, redraws a scene
when it asks for it and caps the frame rate with ``time.sleep``
(``pygame.time`` has no MLX equivalent).
"""

import time

import pygame

from pacman.core.config import GameConfig
from pacman.core.errors import HighscoreError
from pacman.ui.highscores import HighscoreTable
from pacman.ui.log import Logger
from pacman.ui.renderer import Screen
from pacman.ui.scenes import MenuScene, Scene

# Keys with a name of their own.  Letters and digits are handled in
# ``key_name``; everything not listed or typed is ignored.
SPECIAL_KEYS = {
    pygame.K_UP: "up", pygame.K_DOWN: "down",
    pygame.K_LEFT: "left", pygame.K_RIGHT: "right",
    pygame.K_RETURN: "enter", pygame.K_KP_ENTER: "enter",
    pygame.K_ESCAPE: "escape", pygame.K_SPACE: "space",
    pygame.K_BACKSPACE: "backspace",
    pygame.K_F1: "f1", pygame.K_F2: "f2", pygame.K_F3: "f3",
    pygame.K_F4: "f4", pygame.K_F5: "f5", pygame.K_F6: "f6",
    pygame.K_F7: "f7",
}


def key_name(key: int, mod: int) -> str:
    """Return the scene-level name of a pygame key, or "" if unused.

    Letters come out upper-case while shift or caps lock is held, so the
    name prompt can type capitals; scenes that treat letters as commands
    lower them again.
    """
    if key in SPECIAL_KEYS:
        return SPECIAL_KEYS[key]
    if pygame.K_a <= key <= pygame.K_z:
        char = chr(ord("a") + key - pygame.K_a)
        if mod & (pygame.KMOD_SHIFT | pygame.KMOD_CAPS):
            return char.upper()
        return char
    if pygame.K_0 <= key <= pygame.K_9:
        return chr(ord("0") + key - pygame.K_0)
    return ""


class App:
    """Owns the window, the renderer, the highscores and the current scene."""

    def __init__(self, config: GameConfig) -> None:
        """Load the highscores and show the menu (no window yet).

        Args:
            config: the validated settings.
        """
        self.config = config
        self.view = Screen(config)
        self.table = HighscoreTable(config.highscore_filename)
        self.table.load()
        self.running = True
        self.scene: Scene = MenuScene(self)

    def set_scene(self, scene: Scene) -> None:
        """Switch to *scene*; it is drawn on the next frame."""
        self.scene = scene

    def record_score(self, name: str, score: int) -> bool:
        """Add a finished run to the table and save it.

        A save failure is reported but never stops the game.

        Returns:
            True when the score made it into the table.
        """
        added = self.table.add(name, score)
        if added:
            try:
                self.table.save()
            except HighscoreError as exc:
                Logger.warning(str(exc))
        return added

    def run(self) -> None:
        """Open the window and run until the player quits."""
        # Only the display module is started: pygame.init() would also
        # open the audio device, which blocks for a long time on machines
        # without a sound card, and nothing here needs sound.
        pygame.display.init()
        surface = pygame.display.set_mode(
            (self.config.window_width, self.config.window_height))
        pygame.display.set_caption("Pac-Man")
        frame_time = 1.0 / max(1, self.config.fps)
        last = time.perf_counter()
        try:
            while self.running:
                now = time.perf_counter()
                dt = now - last
                last = now
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        name = key_name(event.key, event.mod)
                        if name:
                            self.scene.handle_key(name)
                self.scene.update(dt)
                if self.scene.dirty:
                    self.scene.dirty = False
                    self.scene.draw(surface)
                    pygame.display.flip()
                spare = frame_time - (time.perf_counter() - now)
                if spare > 0:
                    time.sleep(spare)
        finally:
            pygame.display.quit()
