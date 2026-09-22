"""Tiny logging helper writing clear messages to stderr.

Owner: Person A
Contents: get_logger().

Every WARNING and INFO line the subject asks for in V.3 goes through
this logger, so the whole program shares one handler and one format.
"""

import logging
import sys

LOGGER_NAME = "pacman"
MESSAGE_FORMAT = "%(levelname)s: %(message)s"


def get_logger() -> logging.Logger:
    """Return the shared stderr logger, attaching its handler once.

    ``build_config`` calls this once per warning, so the function runs
    many times per run.  It must be idempotent: attaching a second
    handler would print every later message twice.
    """
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(MESSAGE_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
