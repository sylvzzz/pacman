"""Drawing code restricted to pygame calls that exist in MLX.

Owner: Person B
Planned contents: Canvas (pixel-buffer access, hand-rasterised rects/circles/text), Renderer (owns the window; draws menu, pages, maze image cached per level, entities, HUD, pause and end panels).
"""
from pacman.ui.blockfont import Character
import pygame
import os
import time


class Screen:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.mock_walls = {     # this is just for testing in the terminal, not final
            0: "",
            1: "╵",
            2: "╶",
            3: "└",
            4: "╷",
            5: "│",
            6: "┌",
            7: "├",
            8: "╴",
            9: "┘",
            10: "─",
            11: "┴",
            12: "┐",
            13: "┤",
            14: "┬",
            15: "┼",
        }
        # pacman colors for easier access
        self.colors = {
            "green":    (50, 200, 50),
            "blue":     (50, 100, 255),
            "red":      (220, 50, 50),
            "orange":   (255, 165, 0),
            "purple":   (180, 50, 180),
            "black":    (0, 0, 0),
            "brown":    (139, 69, 19),   # rgb colors
            "maroon":   (128, 0, 0),
            "gold":     (255, 215, 0),
            "darkred":  (139, 0, 0),
            "violet":   (238, 130, 238),
            "crimson":  (220, 20, 60),
            "cyan":     (13, 252, 255),
            "yellow":   (255, 255, 0),
            "magenta":  (255, 8, 255),
            "lime":  (80, 252, 7),
        }

    def on_key(self, key, param) -> None:
        # ESC
        if key == 65307:
            os._exit(0)

    def on_close(self, param):
        os._exit(0)

    def write_char(self, char: str, screen, size, x, y) -> None:
        for row, line in enumerate(Character(char).bits):
            for col, bit in enumerate(line):
                if bit == "#":
                    for i in range(size):
                        for j in range(size):
                            screen.set_at((x + col*size + i, y + row*size + j), self.colors["yellow"])

    def write(self, text, screen) -> None:
        size = 5
        x = (self.width - len(text) * 5 * size) // 2
        y = (self.height - 7 * size) // 2
        for ch in text:
            self.write_char(ch, screen, 5, x, y)
            x += 50

    def run(self) -> None:
        from mazegenerator import MazeGenerator

        pygame.init()
        screen = pygame.display.set_mode((self.width, self.height))
        # Create a simple 20x20 maze
        maze_gen = MazeGenerator((20, 20))

        # Get the maze structure
        maze_grid = maze_gen.maze
        shortest_path = maze_gen.shortest_path

        print(f"Maze dimensions: {len(maze_grid[0])}x{len(maze_grid)}")
        print(f"Entry: {maze_gen.maze_entry}, Exit: {maze_gen.maze_exit}")
        print(f"Shortest path length: {len(shortest_path)}")
        print("===== MAZE =====")
        for row in maze_grid:
            for item in row:
                print(self.mock_walls[item], end="")
            print()

        pygame.display.flip()
        running = True
        while running:
            self.write("PAC-MAN", screen)
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                    running = False
            pygame.display.flip()
            time.sleep(0.1)