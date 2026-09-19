"""Drawing code restricted to pygame calls that exist in MLX.

Owner: Person B
Planned contents: Canvas (pixel-buffer access, hand-rasterised rects/circles/text), Renderer (owns the window; draws menu, pages, maze image cached per level, entities, HUD, pause and end panels).
"""
from pacman.ui.blockfont import Character
from pacman.ui.log import Logger
from pacman.ui.maze import Wall, WallStatus, Directions
from pacman.ui.figures import CreatureType, Creature
from mazegenerator import MazeGenerator
import pygame
import random
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

        # Create a simple 20x20 maze
        self.maze_gen = MazeGenerator((20, 20))
        self.maze_gen.generate()
        self.maze_width = self.maze_gen._width
        self.maze_height = self.maze_gen._height

        self.maze_cells = self._populate_cells(random.Random(42), 0.7)
    
        self.player_x = self.spawn_point[0]
        self.player_y = self.spawn_point[1]

        self.LETTER_W = 5
        self.LETTER_H = 7
        self.TEXT_SIZE = 4
        self.LINE_SPACING = 56

        self.wall_thickness = 5
        self.corridor_width = 24
        self.cell_size = self.wall_thickness * 2 + self.corridor_width
        self.band_size = [self.wall_thickness, self.corridor_width, self.wall_thickness]
        self.band_offset = [0, self.wall_thickness, self.wall_thickness + self.corridor_width]
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

        self.current_level = 1

    def _populate_cells(
        self, seed: random.Random, density: float
    ) -> dict[int, dict[int, CreatureType]]:
        """Fill every cell: walls, player spawn, ghost corners and pacgums
        scattered over the remaining corridors."""
        grid = self.maze_gen.maze
        cells: dict[int, dict[int, CreatureType]] = {}
        for row in range(len(grid)):
            cells[row] = {}
            for col in range(len(grid[row])):
                cells[row][col] = (
                    CreatureType.WALL if grid[row][col] == 15
                    else CreatureType.EMPTY
                )

        player_x, player_y = self.maze_gen.maze_entry
        cells[player_y][player_x] = CreatureType.PLAYER
        corners = [
            (0, 0), (0, len(grid[0]) - 1),
            (len(grid) - 1, 0), (len(grid) - 1, len(grid[0]) - 1),
        ]
        for ghost_x, ghost_y in corners:
            cells[ghost_y][ghost_x] = CreatureType.ENEMY

        populated: dict[int, dict[int, CreatureType]] = {}
        for row, row_cells in cells.items():
            populated[row] = {}
            for col, cell_type in row_cells.items():
                if cell_type is not CreatureType.EMPTY:
                    populated[row][col] = cell_type
                elif seed.random() < density:
                    populated[row][col] = CreatureType.SMALL_GUM
                else:
                    populated[row][col] = CreatureType.EMPTY
        return populated

    @property
    def spawn_point(self) -> tuple[int, int]:
        """Célula vazia mais próxima do centro do maze."""
        center_x, center_y = self.maze_width // 2, self.maze_height // 2
        empty_cells = (
            (col, row)
            for row in range(self.maze_height)
            for col in range(self.maze_width)
            if self.maze_cells[row][col] is CreatureType.EMPTY
        )
        return min(
            empty_cells,
            key=lambda pos: abs(pos[0] - center_x) + abs(pos[1] - center_y),
        )

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
        # FUCKING REVIEW THIS
        # CURRENTLY AI FREE OVERDRAWING SUGGESTED SOLUTION

        """

        ===== ORIGINAL ======
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
        
        """

        wall_color = self.colors["blue"]
        logo_color = self.colors["gold"]
        rows, cols = len(maze), len(maze[0])
        width, height = cols * self.cell_size, rows * self.cell_size
        ox = (self.width - width) // 2
        oy = (self.height - height) // 2

        for cy, row in enumerate(maze):
            for cx, w in enumerate(row):
                cell_x = ox + cx * self.cell_size
                cell_y = oy + cy * self.cell_size
                if w.code == 15:
                    screen.fill(logo_color, (cell_x, cell_y, self.cell_size, self.cell_size))
                    continue
                for i, line in enumerate(w.wall):
                    for j, ch in enumerate(line):
                        if ch != " ":
                            screen.fill(wall_color, (cell_x + self.band_offset[j],
                                                    cell_y + self.band_offset[i],
                                                    self.band_size[j],
                                                    self.band_size[i]))

    def cell_to_pixel(self, cx: int, cy: int, ox: int, oy: int, size: int) -> tuple:
        sprite = 7 * size
        return (ox + cx * self.cell_size + (self.cell_size - sprite) // 2,
                oy + cy * self.cell_size + (self.cell_size - sprite) // 2)

    def move_player(self, maze_grid, screen, to_x, to_y) -> None:
        player = Creature(CreatureType.PLAYER, self.colors["yellow"])
        rows, cols = len(maze_grid), len(maze_grid[0])
        ox = (self.width - cols * self.cell_size) // 2
        oy = (self.height - rows * self.cell_size) // 2
        size = 3 # this cannot be float !!
        x, y = self.cell_to_pixel(to_x, to_y, ox, oy, size)
        player.draw(screen, x, y, size)

    def move_creatures(self, maze_grid, screen, to_x, to_y) -> None:
            red_ghost = Creature(CreatureType.ENEMY, self.colors["red"])
            magenta_ghost = Creature(CreatureType.ENEMY, self.colors["magenta"])
            orange_ghost = Creature(CreatureType.ENEMY, self.colors["orange"])
            cyan_ghost = Creature(CreatureType.ENEMY, self.colors["cyan"])

            ghosts = [red_ghost, orange_ghost, cyan_ghost, magenta_ghost]
            
            rows, cols = len(maze_grid), len(maze_grid[0])
            ox = (self.width - cols * self.cell_size) // 2
            oy = (self.height - rows * self.cell_size) // 2
            size = 3 # this cannot be float !!

            x, y = self.cell_to_pixel(len(maze_grid[0]) - 1, len(maze_grid) - 1, ox, oy, size)

            counter = 2
            for ghost in ghosts:
                ghost.draw(screen, x, y, size)
                x, y = self.cell_to_pixel(len(maze_grid[0]) - counter, len(maze_grid) - counter, ox, oy, size)
                counter += 1

    def draw_items(self, maze_grid, screen) -> None:
        small_gum = Creature(CreatureType.SMALL_GUM, self.colors["white"])
        big_gum = Creature(CreatureType.BIG_GUM, self.colors["white"])
        rows, cols = len(maze_grid), len(maze_grid[0])
        ox = (self.width - cols * self.cell_size) // 2
        oy = (self.height - rows * self.cell_size) // 2
        size = 3 # this cannot be float !!

        red_ghost = Creature(CreatureType.ENEMY, self.colors["red"])
        magenta_ghost = Creature(CreatureType.ENEMY, self.colors["magenta"])
        orange_ghost = Creature(CreatureType.ENEMY, self.colors["orange"])
        cyan_ghost = Creature(CreatureType.ENEMY, self.colors["cyan"])

        ghosts = [red_ghost, orange_ghost, cyan_ghost, magenta_ghost]

        ghost_index = 0

        for row in range(0, rows):
            for cell in range(0, cols):
                x, y = self.cell_to_pixel(cell, row, ox, oy, size)
                if self.maze_cells[row][cell] != CreatureType.EMPTY:
                    if self.maze_cells[row][cell] == CreatureType.ENEMY:
                        ghosts[ghost_index].draw(screen, x, y, size)
                        ghost_index += 1
                    elif self.maze_cells[row][cell] == CreatureType.BIG_GUM:
                        big_gum.draw(screen, x, y, size)
                    elif self.maze_cells[row][cell] == CreatureType.SMALL_GUM:
                        small_gum.draw(screen, x, y, size)

    def neighbor_wall(self, direction: Directions) -> int:
        x, y = self.player_x, self.player_y
        if direction == Directions.NORTH:
            return self.maze_gen.maze[y - 1][x]
        if direction == Directions.EAST:
            return self.maze_gen.maze[y][x + 1]
        if direction == Directions.SOUTH:
            return self.maze_gen.maze[y + 1][x]
        return self.maze_gen.maze[y][x - 1]
        
    def can_move(self, direction) -> bool:
        if direction == Directions.NORTH:
            w = Wall(self.neighbor_wall(Directions.NORTH))
            if w.south_is_open:
                return True

        if direction == Directions.EAST:
            w = Wall(self.neighbor_wall(Directions.EAST))
            if w.west_is_open:
                return True

        if direction == Directions.SOUTH:
            w = Wall(self.neighbor_wall(Directions.SOUTH))
            if w.north_is_open:
                return True

        if direction == Directions.WEST:
            w = Wall(self.neighbor_wall(Directions.WEST))
            if w.east_is_open:
                return True

        return False        

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
                                player = {
                                    "name": name,
                                    "points": 0
                                }

                                self.save_player(name, points)
                                screen.fill((0, 0, 0))
                                self.render_maze(screen, self.code_to_walls(self.maze_gen.maze))
                                self.draw_gums(self.maze_gen.maze, screen)
                                self.move_player(self.maze_gen.maze, screen, self.player_x, self.player_y)
                                # self.move_creatures(self.maze_gen.maze, screen, self.player_x, self.player_y)
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
                        if player is not None:
                            self.save_player(player["name"], player["points"])
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
                            self.maze_gen.generate()
                            self.render_maze(screen, self.code_to_walls(self.maze_gen.maze))
                            playing = True

                        if event.key == pygame.K_UP and self.player_y > 0:
                            if self.can_move(Directions.NORTH) is True:
                                self.player_y -= 1
                                if self.maze_cells[self.player_y][self.player_x] == CreatureType.SMALL_GUM:
                                    player["points"] += 15
                                    self.maze_cells[self.player_y][self.player_x] = CreatureType.EMPTY
                                elif self.maze_cells[self.player_y][self.player_x] == CreatureType.BIG_GUM:
                                    player["points"] += 50
                                    self.maze_cells[self.player_y][self.player_x] = CreatureType.EMPTY
                                screen.fill((0, 0, 0))
                                self.render_maze(screen, self.code_to_walls(self.maze_gen.maze))
                                self.draw_items(self.maze_gen.maze, screen)
                                self.move_player(self.maze_gen.maze, screen, self.player_x, self.player_y)
                                # self.move_creatures(self.maze_gen.maze, screen, self.player_x, self.player_y)

                        if event.key == pygame.K_DOWN and self.player_y < len(self.maze_gen.maze) - 1:
                            if self.can_move(Directions.SOUTH) is True:
                                self.player_y += 1
                                if self.maze_cells[self.player_y][self.player_x] == CreatureType.SMALL_GUM:
                                    player["points"] += 15
                                    self.maze_cells[self.player_y][self.player_x] = CreatureType.EMPTY
                                elif self.maze_cells[self.player_y][self.player_x] == CreatureType.BIG_GUM:
                                    player["points"] += 50
                                    self.maze_cells[self.player_y][self.player_x] = CreatureType.EMPTY
                                screen.fill((0, 0, 0))
                                self.render_maze(screen, self.code_to_walls(self.maze_gen.maze))
                                self.draw_items(self.maze_gen.maze, screen)
                                self.move_player(self.maze_gen.maze, screen, self.player_x, self.player_y)
                                # self.move_creatures(self.maze_gen.maze, screen, self.player_x, self.player_y)

                        if event.key == pygame.K_LEFT and self.player_x > 0:
                            if self.can_move(Directions.WEST) is True:
                                self.player_x -= 1
                                if self.maze_cells[self.player_y][self.player_x] == CreatureType.SMALL_GUM:
                                    player["points"] += 15
                                    self.maze_cells[self.player_y][self.player_x] = CreatureType.EMPTY
                                elif self.maze_cells[self.player_y][self.player_x] == CreatureType.BIG_GUM:
                                    player["points"] += 50
                                    self.maze_cells[self.player_y][self.player_x] = CreatureType.EMPTY

                                screen.fill((0, 0, 0))
                                self.render_maze(screen, self.code_to_walls(self.maze_gen.maze))
                                self.draw_items(self.maze_gen.maze, screen)
                                self.move_player(self.maze_gen.maze, screen, self.player_x, self.player_y)
                                # self.move_creatures(self.maze_gen.maze, screen, self.player_x, self.player_y)

                        if event.key == pygame.K_RIGHT and self.player_x < len(self.maze_gen.maze[0]) - 1:
                            if self.can_move(Directions.EAST) is True:
                                self.player_x += 1
                                if self.maze_cells[self.player_y][self.player_x] == CreatureType.SMALL_GUM:
                                    player["points"] += 15
                                    self.maze_cells[self.player_y][self.player_x] = CreatureType.EMPTY
                                elif self.maze_cells[self.player_y][self.player_x] == CreatureType.BIG_GUM:
                                    player["points"] += 50
                                    self.maze_cells[self.player_y][self.player_x] = CreatureType.EMPTY
                                screen.fill((0, 0, 0))
                                self.render_maze(screen, self.code_to_walls(self.maze_gen.maze))
                                self.draw_items(self.maze_gen.maze, screen)
                                self.move_player(self.maze_gen.maze, screen, self.player_x, self.player_y)
                                # self.move_creatures(self.maze_gen.maze, screen, self.player_x, self.player_y)

                        Logger.log(f"X: {self.player_x}, Y: {self.player_y}")

            selected = menu_idx % len(self.menu_options)
            pygame.display.flip()
            time.sleep(0.1)
