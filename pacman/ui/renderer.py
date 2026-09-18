"""Drawing code restricted to pygame calls that exist in MLX.

Owner: Person B
Planned contents: Canvas (pixel-buffer access, hand-rasterised rects/circles/text), Renderer (owns the window; draws menu, pages, maze image cached per level, entities, HUD, pause and end panels).
"""
from pacman.ui.blockfont import Character
from pacman.ui.log import Logger
from pacman.ui.maze import Wall
from pacman.ui.figures import CreatureType, Creature
import pygame
import os
import time



class Screen:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        # pacman colors for easier access
        self.colors = {
            "green":    (50, 200, 50),
            "blue":     (50, 100, 255),
            "red":      (220, 50, 50),
            "orange":   (255, 165, 0),
            "purple":   (180, 50, 180),
            "black":    (0, 0, 0),
            "white":    (255, 255, 255),
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

        self.LETTER_W = 5
        self.LETTER_H = 7
        self.TEXT_SIZE = 4
        self.LINE_SPACING = 56

        # table of letter blocks, filled once
        self.chars = Character(" ").chars

        self.menu_options = ["Play", "View Highscores", "Instructions", "Exit"]
        self.key_chars = {
            pygame.K_a:   "a",
            pygame.K_b:   "b",
            pygame.K_c:   "c",
            pygame.K_d:   "d",
            pygame.K_e:   "e",
            pygame.K_f:   "f",
            pygame.K_g:   "g",
            pygame.K_h:   "h",
            pygame.K_i:   "i",
            pygame.K_j:   "j",
            pygame.K_k:   "k",
            pygame.K_l:   "l",
            pygame.K_m:   "m",
            pygame.K_n:   "n",
            pygame.K_o:   "o",
            pygame.K_p:   "p",
            pygame.K_q:   "q",
            pygame.K_r:   "r",
            pygame.K_s:   "s",
            pygame.K_t:   "t",
            pygame.K_u:   "u",
            pygame.K_v:   "v",
            pygame.K_w:   "w",
            pygame.K_x:   "x",
            pygame.K_y:   "y",
            pygame.K_z:   "z",
            pygame.K_0:   "0",
            pygame.K_1:   "1",
            pygame.K_2:   "2",
            pygame.K_3:   "3",
            pygame.K_4:   "4",
            pygame.K_5:   "5",
            pygame.K_6:   "6",
            pygame.K_7:   "7",
            pygame.K_8:   "8",
            pygame.K_9:   "9",
            pygame.K_MINUS:      "-",
            pygame.K_UNDERSCORE: "_",
            pygame.K_PERIOD:     ".",
        }

    def write_char(self, char: str, screen, size: int, x: int, y: int, color = (255, 255, 0)) -> None:
        block = self.chars.get(char, " ")
        for row, line in enumerate(block):
            for col, bit in enumerate(line):
                if bit == "#":
                    for i in range(size):
                        for j in range(size):
                            screen.set_at((x + col * size + i, y + row * size + j),
                                          color)

    def text_width(self, text: str, size: int) -> int:
        return len(text) * self.LETTER_W * size + (len(text) - 1) * 5

    def text_height(self, texts: list[str], size: int) -> int:
        return (len(texts) - 1) * self.LINE_SPACING + self.LETTER_H * size

    def write(self, text: str, screen, x: int, y: int, size: int, color = (255, 255, 0)) -> None:
        for ch in text:
            self.write_char(ch, screen, size, x, y, color)
            x += self.LETTER_W * size + 5

    def draw(self, content, screen, size: int, x: int, y: int, color = (255, 255, 0)) -> None:
                for row, line in enumerate(content):
                    for col, _ in enumerate(line):
                        for i in range(size):
                            for j in range(size):
                                if col != " ":
                                    screen.set_at((x + col * size + i, y + row * size + j),
                                              color)

    def set_player_name(self, screen, name) -> None:
        screen.fill((0, 0, 0))
        start_y = (self.height - self.text_height(self.menu_options, self.TEXT_SIZE)) // 2
        yellow = self.colors["yellow"]

        x = (self.width - self.text_width("Enter your name:", self.TEXT_SIZE + 2)) // 2
        self.write("Enter your name:", screen, x, start_y - 20 - self.LINE_SPACING, self.TEXT_SIZE + 2, yellow)

        start_y += 30

        x = (self.width - self.text_width(name + "_", self.TEXT_SIZE)) // 2
        self.write(name + "_", screen, x, start_y + 2 * self.LINE_SPACING, self.TEXT_SIZE, self.colors["cyan"])

    def valid_name(self, text: str) -> bool:
        if not text:
            return False
        for char in text:
            if char.lower() not in "abcdefghijklmnopqrstuvwxyz0123456789-._":
                return False
        return True

    def show_menu(self, screen, selected = -1) -> None:
        start_y = (self.height - self.text_height(self.menu_options, self.TEXT_SIZE)) // 2
        yellow = self.colors["yellow"]

        x = (self.width - self.text_width("PAC-MAN", self.TEXT_SIZE + 2)) // 2
        self.write("PAC-MAN", screen, x, start_y - 20 - self.LINE_SPACING, self.TEXT_SIZE + 2, yellow)

        start_y += 30

        for i, text in enumerate(self.menu_options):
            x = (self.width - self.text_width(text, self.TEXT_SIZE)) // 2
            if i == selected:
                self.write(text, screen, x, start_y + i * self.LINE_SPACING, self.TEXT_SIZE, self.colors["white"])
            else:
                self.write(text, screen, x, start_y + i * self.LINE_SPACING, self.TEXT_SIZE, yellow)

    def show_instructions(self, screen) -> None:
        lines = []
        try:
            with open("instructions.txt") as file:
                for line in file:
                    lines.append(line.strip())
        except FileNotFoundError as error:
                Logger.error(f"File {error.filename} not found ...")
                os._exit(1)

        start_y = (self.height - self.text_height(lines, self.TEXT_SIZE)) // 2

        for i, line in enumerate(lines):
            x = (self.width - self.text_width(line, self.TEXT_SIZE)) // 2
            self.write(line, screen, x, start_y + i * self.LINE_SPACING, self.TEXT_SIZE, self.colors["white"])

    def show_highscores(self, screen) -> None:
        import json

        try:
            with open("players.json") as file:
                    players = json.load(file)
        except json.JSONDecodeError:
            Logger.error("Invalid JSON in players data ...")
            os._exit(1)
        except FileNotFoundError as error:
            Logger.error(f"File {error.filename} not found ...")
            os._exit(1)

        start_y = (self.height - self.text_height(players, self.TEXT_SIZE)) // 2
        yellow = self.colors["yellow"]

        x = (self.width - self.text_width("Top 10 Highest Scores", self.TEXT_SIZE + 2)) // 2
        self.write("Top 10 Highest Scores", screen, x, start_y - self.LINE_SPACING, self.TEXT_SIZE + 2, yellow)
        
        start_y += 30

        players = sorted(players, key=lambda player: player['score'], reverse=True)
        rank = 1
        for player in players:
            text = f'{rank}  -  {player["name"]}  -  {player["score"]}'
            x = (self.width - self.text_width(text, self.TEXT_SIZE)) // 2
            if rank > 3:
                self.write(text, screen, x, start_y + rank * self.LINE_SPACING, self.TEXT_SIZE, yellow)
            elif rank == 1:
                self.write(text, screen, x, start_y + rank * self.LINE_SPACING, self.TEXT_SIZE, self.colors["gold"])
            elif rank == 2:
                self.write(text, screen, x, start_y + rank * self.LINE_SPACING, self.TEXT_SIZE, self.colors["white"])
            elif rank == 3:
                self.write(text, screen, x, start_y + rank * self.LINE_SPACING, self.TEXT_SIZE, self.colors["maroon"])
            rank += 1

    def code_to_walls(self, raw_maze: list) -> list:
        return [[Wall(w) for w in row] for row in raw_maze]

    def render_maze(self, screen, maze) -> None:
        tile = 10  # size of a non empty character
        wall = self.colors["blue"]
        rows, cols = len(maze), len(maze[0])
        width, height = cols * 3 * tile, rows * 3 * tile
        ox = (self.width - width) // 2
        oy = (self.height - height) // 2

        for cy, row in enumerate(maze):
            for cx, w in enumerate(row):
                for i, line in enumerate(w.wall):
                    for j, ch in enumerate(line):
                        if ch != " ":
                            screen.fill(wall, (ox + (cx * 3 + j) * tile,
                                               oy + (cy * 3 + i) * tile,
                                               tile, tile))

    def cell_to_pixel(self, cx: int, cy: int, ox: int, oy: int, tile: int,
                      size: int) -> tuple:
        sprite = 7 * size
        return (ox + cx * 3 * tile + (3 * tile - sprite) // 2,
                oy + cy * 3 * tile + (3 * tile - sprite) // 2)
    

    def move_player(self, maze_grid, screen, to_x, to_y) -> None:
        player = Creature(CreatureType.PLAYER, self.colors["yellow"])
        
        tile = 10
        rows, cols = len(maze_grid), len(maze_grid[0])
        ox = (self.width - cols * 3 * tile) // 2
        oy = (self.height - rows * 3 * tile) // 2

        size = 3
        x, y = self.cell_to_pixel(to_x, to_y, ox, oy, tile, size)
        player.draw(screen, x, y, size)
        

    def play(self, screen, maze_gen) -> None:

        # Get the maze structure
        maze_grid = maze_gen.maze
        shortest_path = maze_gen.shortest_path
        
        # print(f"Maze dimensions: {len(maze_grid[0])}x{len(maze_grid)}")
        # print(f"Shortest path length: {len(shortest_path)}")

        self.render_maze(screen, self.code_to_walls(maze_grid))

    def save_player(self, name: str, points: int) -> None:
        import json

        try:
            with open("players.json", "r") as file:
                players = json.load(file)
                players.append({"name": name, "score": points})
            with open("players.json", "w") as file:
                json.dump(players, file, indent=2)
        except json.JSONDecodeError:
            Logger.error("Invalid JSON in players data ...")
            os._exit(1)
        except FileNotFoundError as error:
            Logger.error(f"File {error.filename} not found ...")
            os._exit(1)

    def run(self) -> None:
        from mazegenerator import MazeGenerator

        # Create a simple 20x20 maze
        maze_gen = MazeGenerator((20, 20))
        maze_gen.generate()
        player_x = maze_gen.maze_entry[0]
        player_y = maze_gen.maze_entry[1]

        pygame.init()
        screen = pygame.display.set_mode((self.width, self.height))
        
        pygame.display.flip()
        menu_idx = 0
        running = True
        self.show_menu(screen, menu_idx)
        playing = False
        reading_name = False
        points = 0
        while running:
            for event in pygame.event.get():
                at_home_page = True

                if event.type == pygame.KEYDOWN:
                    if reading_name:
                        if not playing and at_home_page and event.key == pygame.K_LEFT:
                            screen.fill((0, 0, 0))  # review this, since pygame dont have _clear_window of the mlx
                            self.show_menu(screen)
                            reading_name = False
                        if event.key == pygame.K_RETURN:
                            if self.valid_name(name):
                                self.save_player(name, points)
                                screen.fill((0, 0, 0))
                                self.play(screen, maze_gen)
                                self.move_player(maze_gen.maze, screen, player_x, player_y)
                                playing = True
                                reading_name = False
                        elif event.key == pygame.K_BACKSPACE:
                            name = name[:-1]
                            self.set_player_name(screen, name)
                        else:
                            ch = self.key_chars.get(event.key)
                            if ch and len(name) < 28:
                                if ch.isalpha() and event.mod & (pygame.KMOD_SHIFT | pygame.KMOD_CAPS):
                                    ch = ch.upper()
                                elif ch == "-" and event.mod & pygame.KMOD_SHIFT:
                                    ch = "_"
                                name += ch
                                self.set_player_name(screen, name)
                        continue

                    if event.key == pygame.K_q:
                        running = False

                    elif event.key == pygame.K_DOWN and not playing:
                        if menu_idx < len(self.menu_options) - 1:
                            menu_idx += 1
                            self.show_menu(screen, menu_idx)

                    elif event.key == pygame.K_UP and not playing:
                        if menu_idx > 0:
                            menu_idx -= 1
                            self.show_menu(screen, menu_idx)

                    elif event.key == pygame.K_RETURN:
                        Logger.log(self.menu_options[selected])
                        if self.menu_options[selected] == "Exit":
                            running = False

                        if self.menu_options[selected] == "Play":
                            name = ""
                            reading_name = True
                            self.set_player_name(screen, name)
                                
                        if self.menu_options[selected] == "View Highscores":
                            screen.fill((0, 0, 0))  # review this, since pygame dont have _clear_window of the mlx
                            self.show_highscores(screen)
                            at_home_page = False

                        if self.menu_options[selected] == "Instructions":
                            screen.fill((0, 0, 0))  # review this, since pygame dont have _clear_window of the mlx
                            self.show_instructions(screen)
                            at_home_page = False

                    elif not playing and at_home_page and event.key == pygame.K_LEFT:
                        screen.fill((0, 0, 0))  # review this, since pygame dont have _clear_window of the mlx
                        self.show_menu(screen)

                    elif playing is True:
                        if event.key == pygame.K_r:
                            screen.fill((0, 0, 0))
                            maze_gen.generate()
                            self.play(screen, maze_gen)
                            playing = True

                        if event.key == pygame.K_UP and player_y > 0:
                            player_y -= 1
                            screen.fill((0, 0, 0))
                            self.play(screen, maze_gen)
                            self.move_player(maze_gen.maze, screen, player_x, player_y)

                        if event.key == pygame.K_DOWN and player_y < len(maze_gen.maze) - 1:
                            player_y += 1
                            screen.fill((0, 0, 0))
                            self.play(screen, maze_gen)
                            self.move_player(maze_gen.maze, screen, player_x, player_y)

                        if event.key == pygame.K_LEFT and player_x > 0:
                            player_x -= 1
                            screen.fill((0, 0, 0))
                            self.play(screen, maze_gen)
                            self.move_player(maze_gen.maze, screen, player_x, player_y)

                        if event.key == pygame.K_RIGHT and player_x < len(maze_gen.maze[0]) - 1:
                            player_x += 1
                            screen.fill((0, 0, 0))
                            self.play(screen, maze_gen)
                            self.move_player(maze_gen.maze, screen, player_x, player_y)

                        Logger.success(f"X: {player_x}, Y: {player_y}")

            selected = menu_idx % len(self.menu_options)
            pygame.display.flip()
            time.sleep(0.1)
