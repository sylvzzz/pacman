"""Screens of the application: menu, pages, gameplay and game end.

Owner: Person B
Planned contents: Scene base, MenuScene, HighscoresScene, InstructionsScene, PlayScene (pause overlay, cheat keys), EndScene (name entry), new_game().
"""
import enum


class Directions(enum.Enum):
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3

class WallStatus(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class Wall:
    def __init__(self, code: int) -> None:
        self.code = code
        self.wall = self.bit_to_wall()
        self.north_is_open = self.north_open()
        self.south_is_open = self.south_open()
        self.east_is_open = self.east_open()
        self.west_is_open = self.west_open()

    def north_open(self) -> bool:
        number = format(self.code, '04b')
        if str(number)[3] == "1":
            return False
        return True

    def south_open(self) -> bool:
            number = format(self.code, '04b')
            if str(number)[1] == "1":
                return False
            return True

    def east_open(self) -> bool:
            number = format(self.code, '04b')
            if str(number)[2] == "1":
                return False
            return True

    def west_open(self) -> bool:
            number = format(self.code, '04b')
            if str(number)[0] == "1":
                return False
            return True

    def bit_to_wall(self) -> list:
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
        return wall_bits.get(self.code, "")