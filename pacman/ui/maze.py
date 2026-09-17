"""Screens of the application: menu, pages, gameplay and game end.

Owner: Person B
Planned contents: Scene base, MenuScene, HighscoresScene, InstructionsScene, PlayScene (pause overlay, cheat keys), EndScene (name entry), new_game().
"""

class Wall:
    def __init__(self, code: int) -> None:
        self.code = code
        self.wall = self.bit_to_wall()

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