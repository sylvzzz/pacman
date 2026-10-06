"""Wall shapes: the box-drawing tile for each of the 16 wall codes.

Owner: Person B
Contents: Directions, WallStatus, Wall.

A code is the maze package's 4-bit cell mask (a set bit is a wall).
``Wall`` reads which sides are open and picks the 3x3 shape the renderer
rasterises.
"""

import enum


class Directions(enum.Enum):
    """The four sides of a cell."""

    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3


class WallStatus(enum.Enum):
    """Whether a side is open or closed."""

    OPEN = "open"
    CLOSED = "closed"


class Wall:
    """One cell's walls, decoded from its 4-bit code."""

    def __init__(self, code: int) -> None:
        """Decode *code* into a shape and the four open flags."""
        self.code = code
        self.wall = self.bit_to_wall()
        self.north_is_open = self.north_open()
        self.south_is_open = self.south_open()
        self.east_is_open = self.east_open()
        self.west_is_open = self.west_open()

    def _bit(self, index: int) -> str:
        """Return the character at *index* of the 4-bit binary code."""
        return format(self.code, "04b")[index]

    def north_open(self) -> bool:
        """Return True when the north side has no wall."""
        return self._bit(3) != "1"

    def south_open(self) -> bool:
        """Return True when the south side has no wall."""
        return self._bit(1) != "1"

    def east_open(self) -> bool:
        """Return True when the east side has no wall."""
        return self._bit(2) != "1"

    def west_open(self) -> bool:
        """Return True when the west side has no wall."""
        return self._bit(0) != "1"

    def bit_to_wall(self) -> tuple[str, ...]:
        """Return the 3x3 box-drawing rows for this code."""
        wall_bits = {
            0: (
                "   ",
                "   ",
                "   ",
            ),
            1: (
                "───",
                "   ",
                "   ",
            ),
            2: (
                "  │",
                "  │",
                "  │",
            ),
            3: (
                "──┐",
                "  │",
                "  │",
            ),
            4: (
                "   ",
                "   ",
                "───",
            ),
            5: (
                "───",
                "   ",
                "───",
            ),
            6: (
                "  │",
                "  │",
                "──┘",
            ),
            7: (
                "──┐",
                "  │",
                "──┘",
            ),
            8: (
                "│  ",
                "│  ",
                "│  ",
            ),
            9: (
                "┌──",
                "│  ",
                "│  ",
            ),
            10: (
                "│ │",
                "│ │",
                "│ │",
            ),
            11: (
                "┌─┐",
                "│ │",
                "│ │",
            ),
            12: (
                "│  ",
                "│  ",
                "└──",
            ),
            13: (
                "┌──",
                "│  ",
                "└──",
            ),
            14: (
                "│ │",
                "│ │",
                "└─┘",
            ),
            15: (
                "┌─┐",
                "│ │",
                "└─┘",
            ),
        }
        return wall_bits.get(self.code, ())
