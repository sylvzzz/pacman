"""Application loop: window, timing, event dispatch and scene switching.

Owner: Person B
Planned contents: App (one Renderer, one HighscoreTable, the current Scene; delta-time loop using the time module), _char_for_key().
"""

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