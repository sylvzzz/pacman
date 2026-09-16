"""Application loop: window, timing, event dispatch and scene switching.

Owner: Person B
Planned contents: App (one Renderer, one HighscoreTable, the current Scene; delta-time loop using the time module), _char_for_key().
"""

"""
from Mlx import Mlx

def mymouse(button, x, y, mystuff):
    print(f"Got mouse event! button {button} at {x},{y}.")

def mykey(keynum, mystuff):
    print(f"Got key {keynum}, and got my stuff back:")
    print(mystuff)
    if keynum == 32:
        m.mlx_mouse_hook(win_ptr, None, None)

m = Mlx()
mlx_ptr = m.mlx_init()
win_ptr = m.mlx_new_window(mlx_ptr, 200, 200, "toto")
m.mlx_clear_window(mlx_ptr, win_ptr)
m.mlx_string_put(mlx_ptr, win_ptr, 20, 20, 255, "Hello PyMlx!")
(ret, w, h) = m.mlx_get_screen_size(mlx_ptr)
print(f"Got screen size: {w} x {h} .")

stuff = [1, 2]
m.mlx_mouse_hook(win_ptr, mymouse, None)
m.mlx_key_hook(win_ptr, mykey, stuff)

m.mlx_loop(mlx_ptr)
"""

import os


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
        self.color = {
            "red": 0xFF0000,
            "orange": 0xFF7F00,
            "yellow": 0xFFFF00,
            "green": 0x00FF00,
            "blue": 0x0000FF,
            "indigo": 0x4B0082,
            "violet": 0x8F00FF,
            "pacman": 0xFFFF00,
            "wall": 0x2121DE,
            "dot": 0xFFFFFF,
            "power_pellet": 0x66FF66,
            "blinky": 0xFF0000,
            "pinky": 0xFFC0CB,
            "inky": 0x00FFFF,
            "clyde": 0xFFB852,
            "ghost_door": 0xFFFFFF,
            "score": 0xFFFFFF,
            "background": 0x000000,
        }

    def on_key(self, key, param) -> None:
        # ESC
        if key == 65307:
            os._exit(0)

    def on_close(self, param):
        os._exit(0)

    def open_window(self) -> None:
        from mlx import Mlx
        # NOTE - my PC is BGR instead of RGB so BLUE outputed RED

        m = Mlx()
        mlx_ptr = m.mlx_init()
        win_ptr = m.mlx_new_window(mlx_ptr, self.width, self.height, "toto")
        m.mlx_clear_window(mlx_ptr, win_ptr)
        m.mlx_string_put(mlx_ptr, win_ptr, 20, 20, 0x00FF0000, "A")
        ret, w, h = m.mlx_get_screen_size(mlx_ptr)
        print(f"Got screen size: {w} x {h} .")

        m.mlx_key_hook(win_ptr, self.on_key, None)

        m.mlx_loop(mlx_ptr)

    def run(self) -> None:
        from mazegenerator import MazeGenerator

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

        self.open_window()