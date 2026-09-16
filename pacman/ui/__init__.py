"""UI: rendering, screens, input and app loop. Owner: Person B.

Imports ``pacman.core``; only ``renderer`` and ``app`` may call pygame.
"""

from pacman.ui.renderer import Screen
from pacman.ui.blockfont import Character

__all__ = ["Screen", "Character"]