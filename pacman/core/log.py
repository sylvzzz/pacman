"""Tiny logging helper writing clear messages to stderr.

Owner: Person A
Planned contents: get_logger().
"""

import logging
import sys

LOGGER_NAME = "pacman"


def get_logger() -> logging.Logger:
    """Return the shared stderr logger, creating its handler once."""
    logger = logging.getLogger(LOGGER_NAME)
    
    return logger