import enum


class CreatureType(enum.Enum):
    PLAYER = "player"
    ENEMY = "enemy"
    BIG_GUM = "big_gum"
    SMALL_GUM = "small_gum"


class Creature:
    def __init__(self, type: CreatureType, color: tuple) -> None:
        self.type = type
        self.color = color

    @property
    def bits(self) -> tuple:
        """
        . - black/nothing
        # - color
        % - pupil
        0 - outer eye
        """
        entities_bits = {
            CreatureType.PLAYER: (
                ".#####.",
                "#######",
                "######.",
                "#####..",
                "######.",
                "#######",
                ".#####.",
            ),
            CreatureType.ENEMY: (
                "..####..",
                ".######.",
                "##00##00",
                "##0%##0%",
                "########",
                "########",
                "##.##.##.",
            ),
            CreatureType.SMALL_GUM: (
                ".....",
                "..#..",
                ".###.",
                "..#..",
                ".....",
            ),
            CreatureType.BIG_GUM: (
                "..###..",
                ".#####.",
                "#######",
                "#######",
                "#######",
                ".#####.",
                "..###..",
            ),
        }
        return entities_bits[self.type]

    def draw(self, screen, x: int, y: int, size: int) -> None:
        eye_white = (255, 255, 255)
        eye_pupil = (50, 100, 255)
        for row, line in enumerate(self.bits):
            for col, bit in enumerate(line):
                if bit == "#":
                    color = self.color
                elif bit == "0":
                    color = eye_white
                elif bit == "%":
                    color = eye_pupil
                else:
                    continue
                screen.fill(color, (x + col * size, y + row * size,
                                    size, size))
