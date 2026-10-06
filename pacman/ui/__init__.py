"""UI: rendering, screens, input and app loop.

Owner: Person B.  Imports ``pacman.core``; only ``renderer`` and ``app`` may
call pygame.

``log`` is stdlib-only, so it is imported first and is therefore always
available: a machine without pygame can report the missing dependency
through ``Logger`` instead of dying with a traceback at import time.

The names below need pygame, so they are imported defensively.  When one of
them is missing it is simply absent from this module and ``IMPORT_ERROR``
holds the cause -- ``Screen`` is never touched before the entry point has
checked that, and importing a name that needs pygame then fails loudly,
which is the honest outcome.
"""

from pacman.ui.log import Logger

IMPORT_ERROR: ImportError | None

__all__ = ["Logger", "IMPORT_ERROR"]

try:
    from pacman.ui.app import App
    from pacman.ui.renderer import Screen
    from pacman.ui.blockfont import Character
    from pacman.ui.maze import Wall, WallStatus, Directions
    from pacman.ui.figures import CreatureType
except ImportError as exc:  # pygame / mazegenerator not installed
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None
    __all__ += ["App", "Screen", "Character", "Wall", "WallStatus",
                "Directions", "CreatureType"]
