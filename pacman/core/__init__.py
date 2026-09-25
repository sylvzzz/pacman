"""Core: headless game model.

Owner: Person A.  Nothing in this package may import pygame or ``pacman.ui``.
"""

from pacman.core.config import GameConfig, load_config
from pacman.core.maze_loader import _generate

__all__ = ["GameConfig", "load_config", "_generate"]
