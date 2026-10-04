"""Drawing code restricted to pygame calls that exist in MLX.

Owner: Person B
Planned contents: Canvas (pixel-buffer access, hand-rasterised
  rects/circles/text), Renderer (owns the window; draws menu, pages, maze image
  cached per level, entities, HUD, pause and end panels).
"""
from pacman.ui.blockfont import Character
from pacman.ui.log import Logger
from pacman.ui.maze import Wall
from pacman.ui.figures import (CreatureType, facing_of, ghost,
                                pacman, shade)
from pacman.ui.playfield import GHOST_COLORS, Playfield
from pacman.core.entities import Direction, GhostState
from pacman.core.maze_loader import _generate
import math
import os
import pygame
import random
import time

# Arrow keys onto the core's directions.  The two enums disagree on
# purpose -- the core counts tiles the way the model reads them (UP is
# -y), the UI counts them the way a compass does -- so the translation
# lives in one table instead of being re-derived at each call site.
# Seed for the home menu's decorative scatter.  Any fixed number works;
# it just has to be a constant, or the wallpaper changes between runs.
MENU_DECOR_SEED = 20240
#: Pellets scattered per free band on the home menu.
MENU_DECOR_PELLETS = 14

KEY_TO_DIRECTION = {
    pygame.K_UP: Direction.UP,
    pygame.K_DOWN: Direction.DOWN,
    pygame.K_LEFT: Direction.LEFT,
    pygame.K_RIGHT: Direction.RIGHT,
}

# Sprite diameter, in pixels, of the player, a ghost and a pellet.  Kept
# just under the corridor so entities never overlap a wall.
# Gap between the maze and the edge of the window, and the floor for
# ``fit_cell_size`` so a cramped level degrades into a small maze rather
# than a broken one.
MARGIN = 14
MIN_CELL = 22

# The 16 wall shapes, indexed by the code the maze generator emits.  Built
# once: ``Wall`` re-parses the code's binary form in its constructor, and
# only the shape is needed here.
WALL_MASKS = {code: Wall(code).wall for code in range(16)}


class Screen:
    def __init__(self, config) -> None:
        self.config = config
        self.width = config.window_width
        self.height = config.window_height
        self.points_pacgum = config.points_per_pacgum
        self.points_super = config.points_per_super_pacgum
        # pacman colors for easier access
        self.colors = {
            "green":    (50, 200, 50),
            "blue":     (50, 100, 255),
            "red":      (220, 50, 50),
            "orange":   (255, 165, 0),
            "purple":   (180, 50, 180),
            # "black":    (0, 0, 0),
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
            # The maze is a dark room and the walls are the only light in
            # it.  Each wall is drawn as three nested rectangles -- a wide
            # dim halo, a body, and a bright core -- because MLX cannot
            # blur, so the glow has to be built from solid bands.
            "void":      (4, 4, 14),
            "pellet":    (255, 246, 222),
            # Unselected menu items and hints: present but quiet.
            "slate":     (104, 130, 170),
            "halo":      (10, 22, 72),
            "wall":      (28, 68, 190),
            "wall_core": (108, 190, 255),
        }
        # How long one full animation cycle takes, in seconds.  These are
        # deliberately slow: the eye is on the maze constantly, so motion
        # here is ambience and must never pull focus off the next corridor.
        self.CHOMP_PERIOD = 0.19
        self.PELLET_PERIOD = 1.25
        self.GHOST_PERIOD = 0.42
        self.FRIGHT_FLASH = 0.26

        # Create a simple 20x20 maze
        self.current_level = 0
        self.cheat_options = ["INVICIBILITY", "SKIP LEVEL", "FREEZE GHOSTS", "2x SPEED", "EXIT"]
        self.levels = config.levels
        self.seed = config.seed
        self.mw, self.mh = (self.levels[self.current_level].width,
                            self.levels[self.current_level].height)
        self.maze_gen = _generate(self.mw, self.mh, self.seed)
        self.maze_cells = self._populate_cells()

        # The core model for the level being played.  None until a game
        # starts; the menu does not need one.
        self.playfield: Playfield | None = None
        self.points = 0
        # Drives every sprite animation from one monotonic clock, so the
        # mouth, the skirt and the power pellets stay in step and can never
        # drift apart or restart on their own.
        self.anim = 0.0
        self.dt = 0.0
        self.popups: list[dict] = []
        self.stamps: dict[float, list] = {}

        self.maze_width = self.maze_gen._width
        self.maze_height = self.maze_gen._height

        self.LETTER_W = 5
        self.LETTER_H = 7
        self.TEXT_SIZE = 4
        self.LINE_SPACING = 56

        self.cell_size = 34
        self.band_size = [5, 24, 5]
        self.band_offset = [0, 5, 29]
        # table of letter blocks, filled once
        self.chars = Character(" ").chars

        self.menu_options = ["Play", "View Highscores", "Instructions", "Exit"]
        self._decor = None
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
        }

        self.cheats_activated = {
            "INVICIBILITY": False,
            "SKIP LEVEL": False,
            "FREEZE GHOSTS": False,
            "2x SPEED": False,
        }

    def _populate_cells(self) -> dict[int, dict[int, CreatureType]]:
        """Mark every cell as wall or corridor.

        Only the walls are decided here, because they are the one thing the
        drawing code needs that the core model does not hand over as plain
        numbers.  Pellets, the player and the ghosts all come from the core
        model, so nothing is placed here that could disagree with it.
        """
        grid = self.maze_gen.maze
        cells: dict[int, dict[int, CreatureType]] = {}
        for row in range(len(grid)):
            cells[row] = {}
            for col in range(len(grid[row])):
                cells[row][col] = (
                    CreatureType.WALL if grid[row][col] == 15
                    else CreatureType.EMPTY
                )
        return cells

    def write_char(self, char: str, screen, size: int, x: int, y: int, color = (255, 255, 0)) -> None:
        block = self.chars.get(char, " ")
        for row, line in enumerate(block):
            for col, bit in enumerate(line):
                if bit == "#":
                    # One fill per block rather than one set_at per pixel: a
                    # glyph pixel *is* a solid size x size square, so this is
                    # the same image for size**2 fewer calls.  The HUD is the
                    # only text on screen, but it is redrawn every frame.
                    screen.fill(color, (x + col * size, y + row * size,
                                        size, size))

    def text_width(self, text: str, size: int, tracking: int = 5) -> int:
        return len(text) * self.LETTER_W * size + (len(text) - 1) * tracking

    def text_height(self, texts: list[str], size: int) -> int:
        return (len(texts) - 1) * self.LINE_SPACING + self.LETTER_H * size

    def write(self, text: str, screen, x: int, y: int, size: int,
              color=(255, 255, 0), tracking: int = 5) -> None:
        """Draw *text* with its top-left at ``(x, y)``.

        Args:
            tracking: extra pixels between glyphs.  Opening the tracking up
                on a title is what separates a heading from a label without
                needing a second font, which MLX does not have.
        """
        for ch in text:
            self.write_char(ch, screen, size, x, y, color)
            x += self.LETTER_W * size + tracking

    def hline(self, screen, x: int, y: int, w: int, color: tuple,
              thickness: int = 2) -> None:
        """Draw a horizontal rule, used to separate a title from its list."""
        if w > 0:
            screen.fill(color, (x, y, w, thickness))

    def set_player_name(self, screen, name) -> None:
        """Prompt for the run's name, with a caret while there is room.

        The caret is a solid underscore, not a blink: MLX has no clock to
        drive one, and a steady caret is easier to aim at anyway.
        """
        self.clear(screen)
        start_y = (self.height
                   - self.text_height(self.menu_options, self.TEXT_SIZE)) // 2
        self.draw_line(screen, "Enter your name",
                       start_y - 20 - self.LINE_SPACING,
                       self.TEXT_SIZE + 2, self.colors["gold"])
        caret = name + "_" if len(name) < 10 else name
        self.draw_line(screen, caret, start_y + 2 * self.LINE_SPACING,
                       self.TEXT_SIZE, self.colors["cyan"])

    def valid_name(self, text: str) -> bool:
        if not text:
            return False
        for char in text:
            if char.lower() not in "abcdefghijklmnopqrstuvwxyz0123456789":
                return False
        return True

    def draw_panel(self, screen, title: str, items: list, selected: int,
                   hint: str = "", colors: list | None = None,
                   suffixes: list | None = None) -> None:
        """Draw a titled list of choices, centred, with the selection marked.

        Every menu used to be its own copy of the same loop, which is why
        they all looked identical and why the selected row was only
        distinguishable by colour.  Selection now also carries *position* --
        a marker in the gutter -- so it survives colour blindness and reads
        in one pass instead of two.

        Nothing here animates.  The cursor is moved with the arrow keys
        hundreds of times a session, and animating a keyboard-driven thing
        only makes it feel like it is lagging behind you.

        Args:
            title: heading, drawn large and letter-spaced.
            items: the row labels, top to bottom.
            selected: index of the highlighted row, or -1 for none.
            hint: controls line along the bottom.
            colors: optional colour per row, overriding the default.
            suffixes: optional ``(text, colour)`` per row, right-aligned in a
                gutter.  Used for the cheat toggles, whose state has to line
                up down the screen independently of the labels.
        """
        scale = self.hud_scale()
        title_scale = scale + 3
        item_scale = scale + 1
        top = max(scale * 4, self.height // 6)

        tracking = scale * 2
        title_w = self.text_width(title, title_scale, tracking)
        self.write(title, screen, (self.width - title_w) // 2, top,
                   title_scale, self.colors["gold"], tracking)
        self.hline(screen, (self.width - title_w) // 2,
                   top + self.LETTER_H * title_scale + scale * 2,
                   title_w, self.colors["halo"], max(2, scale // 2))

        y = top + self.LETTER_H * title_scale + scale * 7
        for i, text in enumerate(items):
            chosen = i == selected
            if colors is not None:
                color = colors[i]
            else:
                color = (self.colors["yellow"] if chosen
                         else self.colors["slate"])
            x = (self.width - self.text_width(text, item_scale)) // 2
            if chosen:
                # The marker is its own glyph in its own colour, in the
                # gutter left of the label, so the labels stay aligned and
                # the cursor reads as chrome rather than as part of a word.
                self.write("*", screen, x - item_scale * 7, y, item_scale,
                           self.colors["cyan"])
            self.write(text, screen, x, y, item_scale, color)
            if suffixes is not None:
                tail, tail_color = suffixes[i]
                if tail:
                    # Right-aligned at a fixed x, not offset by the label
                    # width: the whole point of a state column is that the
                    # states line up with each other.
                    self.write(tail, screen, self.width - MARGIN
                               - self.text_width(tail, item_scale), y,
                               item_scale, tail_color)
            y += self.LETTER_H * item_scale + scale * 3

        if hint:
            # draw_line, not write: the controls line is the widest thing
            # on the panel and used to run off both edges of the window.
            self.draw_line(screen, hint, self.height - scale * 11, scale,
                           self.colors["slate"])

    def menu_bands(self, radius: int) -> tuple:
        """Return the two ``(low, high)`` bands the home panel leaves empty.

        Same vertical arithmetic as ``draw_panel``, so the scatter can
        never land on the title or a row.  Inset by the ghost sprite's
        real extent rather than its radius: a ghost is taller than it is
        wide, and centring it in a band that only clears the radius drops
        its feet on the title.  ``test_menu_decor_lands_only_in_the_gutters``
        is what catches it if the panel layout ever moves.
        """
        scale = self.hud_scale()
        top = max(scale * 4, self.height // 6)
        rows = top + self.LETTER_H * (scale + 3) + scale * 7
        rows += len(self.menu_options) * (self.LETTER_H * (scale + 1)
                                          + scale * 3)
        tall = radius * 2
        return ((tall, top - tall),
                (rows + tall, self.height - scale * 13 - tall))

    def menu_corners(self, radius: int) -> tuple:
        """Return one ``(x0, x1, y0, y1)`` box per screen corner.

        A ghost in each corner reads as a deliberate arrangement; the same
        four ghosts scattered at random read as debris.
        """
        (top_lo, top_hi), (bot_lo, bot_hi) = self.menu_bands(radius)
        pad = self.hud_scale() * 7
        half = self.width // 2
        left = (pad + radius, half)
        right = (half, self.width - pad - radius)
        return ((right, (top_lo, top_hi)),
                (left, (top_lo, top_hi)),
                (left, (bot_lo, bot_hi)),
                (right, (bot_lo, bot_hi)))

    def menu_decor(self) -> tuple:
        """Pick the home menu's ghost and pellet scatter, once per process.

        One ghost per corner, in ``GHOST_COLORS`` order: upper right,
        upper left, lower left, lower right.  Rolled once from a fixed
        seed and then reused -- the panel repaints on every arrow key and
        every frame of the loop, so picking fresh positions each time
        would make the screen boil, and a fixed seed keeps the wallpaper
        identical between runs.
        """
        if self._decor is None:
            rng = random.Random(MENU_DECOR_SEED)
            scale = self.hud_scale()
            radius = scale * 4
            ghosts = []
            for color, (xs, ys) in zip(GHOST_COLORS, self.menu_corners(radius)):
                ghosts.append((rng.randint(xs[0], max(xs)),
                               rng.randint(ys[0], max(ys)),
                               rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1))),
                               color))
            pad = scale * 7
            span = self.width - 2 * pad
            slot = span / MENU_DECOR_PELLETS
            pellets = []
            # Radii off the board's own: a plain pellet there is about
            # three pixels and a power pellet about six, which is what
            # gives them the stepped edge instead of a smooth bubble.
            #
            # Even slots with a jitter inside each, not a free draw per
            # pellet: 28 uniform randoms clump, and a bald patch reads as
            # a mistake where an even spread reads as scattered.
            for low, high in self.menu_bands(scale // 2):
                for i in range(MENU_DECOR_PELLETS):
                    big = rng.random() < 0.22
                    pellets.append((
                        round(pad + slot * (i + rng.uniform(0.2, 0.8))),
                        rng.randint(low, max(low, high)),
                        scale if big else scale // 2))
            self._decor = (ghosts, pellets)
        return self._decor

    def draw_menu_decor(self, screen) -> None:
        """Scatter the four corner ghosts and some pellets round the menu."""
        ghosts, pellets = self.menu_decor()
        radius = self.hud_scale() * 4
        body = self.colors["pellet"]
        halo = shade(body, 0.5)
        for x, y, facing, color in ghosts:
            ghost(screen, x, y, radius, self.colors[color], facing)
        power = self.hud_scale()
        for x, y, size in pellets:
            if size == power:
                self.stamp_pellet(screen, x, y, size + 1.5, halo)
            self.stamp_pellet(screen, x, y, size, body)

    def show_menu(self, screen, selected = -1) -> None:
        """Draw the main menu over whatever is already on screen."""
        self.draw_menu_decor(screen)
        self.draw_panel(screen, "PAC-MAN", self.menu_options, selected,
                        "ARROWS MOVE    ENTER SELECT    Q QUIT")

    def pause_menu(self, screen, selected = -1) -> None:
        """Draw the pause overlay."""
        self.draw_panel(screen, "PAUSED", ["Resume", "Main Menu"], selected,
                        "ESC RESUME")

    def cheat_menu(self, screen, selected = -1) -> None:
        """Draw the cheat list with each toggle's state in its own column."""
        suffixes = []
        for name in self.cheat_options:
            if name == "EXIT":
                suffixes.append(("", self.colors["slate"]))
            else:
                on = self.cheats_activated[name]
                suffixes.append(("ON" if on else "OFF", self.colors["green"]
                                 if on else self.colors["red"]))
        self.draw_panel(screen, "CHEATS", self.cheat_options, selected,
                        "ARROWS MOVE    ENTER TOGGLE    Q BACK", None, suffixes)

    def show_instructions(self, screen) -> None:
        lines = []
        try:
            with open("instructions.txt") as file:
                for line in file:
                    lines.append(line.strip())
        except FileNotFoundError as error:
            Logger.error(f"File {error.filename} not found ...")
            os._exit(1)

        scale = self.hud_scale()
        title = "HOW TO PLAY"
        tracking = scale * 2
        title_scale = scale + 3
        top = max(scale * 4, self.height // 6)

        # Shrink the body until the whole file fits above the bottom edge.
        # instructions.txt is longer than the window at full size and used
        # to run off the bottom, so the last line was never readable.
        budget = self.height - top - self.LETTER_H * title_scale - scale * 9
        size = max(2, scale - 1)
        while size > 2:
            spacing = self.LETTER_H * size + scale * 2
            needed = sum(spacing // 2 if not text else spacing
                         for text in lines)
            if needed <= budget:
                break
            size -= 1
        spacing = self.LETTER_H * size + scale * 2

        title_w = self.text_width(title, title_scale, tracking)
        self.write(title, screen, (self.width - title_w) // 2, top,
                   title_scale, self.colors["gold"], tracking)
        self.hline(screen, (self.width - title_w) // 2,
                   top + self.LETTER_H * title_scale + scale * 2,
                   title_w, self.colors["halo"], max(2, scale // 2))
        y = top + self.LETTER_H * title_scale + scale * 6
        for line in lines:
            if not line:
                y += spacing // 2
                continue
            # draw_line shrinks to fit: the longest line in
            # instructions.txt is wider than the window at this scale and
            # used to be clipped at both edges.
            self.draw_line(screen, line, y, size, self.colors["slate"])
            y += spacing

    def show_highscores(self, screen) -> None:
        import json

        try:
            with open("players.json") as file:
                players_json = json.load(file)
        except json.JSONDecodeError:
            Logger.error("Invalid JSON in players data ...")
            os._exit(1)
        except FileNotFoundError as error:
            Logger.error(f"File {error.filename} not found ...")
            os._exit(1)

        title = "Top 10 Highest Scores"
        # Sort before slicing: .items() is a view and cannot be subscripted,
        # and slicing first would take the first ten names in file order
        # rather than the ten highest scores.
        players = sorted(players_json.items(),
                         key=lambda item: item[1]['score'],
                         reverse=True)[:10]
        start_y = (self.height - self.text_height(players, self.TEXT_SIZE)) // 2

        self.draw_line(screen, title, start_y - self.LINE_SPACING,
                       self.TEXT_SIZE + 2, self.colors["gold"])

        start_y += 30

        # Podium reads first, the rest recedes.  Nothing down here may be
        # darker than slate: maroon was 2.6:1 on this background, which is
        # a line you cannot actually read.
        medals = {1: self.colors["gold"], 2: self.colors["white"],
                  3: self.colors["yellow"]}
        for rank, (name, player_data) in enumerate(players, start=1):
            self.draw_line(screen, f'{rank}  -  {name}  -  {player_data["score"]}',
                           start_y + rank * self.LINE_SPACING,
                           self.TEXT_SIZE,
                           medals.get(rank, self.colors["slate"]))

    def code_to_walls(self, raw_maze: list) -> list:
        return [[Wall(w) for w in row] for row in raw_maze]

    def build_maze_layers(self) -> None:
        """Flatten the maze into a list of ``(rect, colour)`` to stamp.

        The walls never move, so the geometry is worked out once per level
        and every frame just replays the list.  That is what makes the
        three-band neon cheap enough to draw: the halo, body and core of
        each wall band are separate opaque rectangles, since MLX has no
        blur to fake a glow with.
        """
        self.maze_layers = []
        halo, body, core = (self.colors["halo"], self.colors["wall"],
                            self.colors["wall_core"])
        ox, oy = self.maze_origin()
        grid = self.maze_gen.maze
        pad = self.halo_pad()
        for cy, row in enumerate(grid):
            for cx, code in enumerate(row):
                x0 = ox + cx * self.cell_size
                y0 = oy + cy * self.cell_size
                if code == 15:
                    # The "42" glyph: all four walls set, so its mask is a
                    # hollow box and the shape collapses into its own
                    # outline.  Fill the cell instead.  These cells are
                    # never on the border -- core only emits code 15
                    # interior -- so this cannot slab over a corridor.
                    self.maze_layers.append(
                        ((x0 - pad, y0 - pad,
                          self.cell_size + 2 * pad,
                          self.cell_size + 2 * pad), halo))
                    self.maze_layers.append(
                        ((x0, y0, self.cell_size, self.cell_size), body))
                    t = max(1, self.core_thickness())
                    self.maze_layers.append(
                        ((x0 + t, y0 + t, self.cell_size - 2 * t,
                          self.cell_size - 2 * t), core))
                    continue
                for i, line in enumerate(WALL_MASKS[code]):
                    for j, ch in enumerate(line):
                        if ch == " ":
                            continue
                        x = x0 + self.band_offset[j]
                        y = y0 + self.band_offset[i]
                        w = self.band_size[j]
                        h = self.band_size[i]
                        self.maze_layers.append(
                            ((x - pad, y - pad, w + 2 * pad, h + 2 * pad),
                             halo))
                        self.maze_layers.append(((x, y, w, h), body))
                        if j == 1 and i == 1:
                            continue               # corridor stays open
                        # The bright core sits inside the band, so the walls
                        # read as lit tubes rather than flat slabs.
                        t = max(1, self.core_thickness())
                        self.maze_layers.append(((x + t, y + t,
                                                   w - 2 * t, h - 2 * t),
                                                  core))

    def entity_size(self) -> int:
        """Diameter in pixels of the player, a ghost or a power pellet.

        Derived from the corridor rather than fixed, so an entity keeps the
        same presence-to-corridor ratio on a 14x10 level and a 19x14 one
        instead of shrinking out of sight on the bigger boards.
        """
        corridor = self.cell_size - 2 * self.band_size[0]
        return max(10, round(corridor * 0.74))

    def halo_pad(self) -> int:
        """How far a wall's glow spreads, in pixels."""
        return max(1, round(self.cell_size * 0.055))

    def core_thickness(self) -> int:
        """Thickness of the lit line inside a wall band, in pixels."""
        return max(1, round(self.cell_size * 0.045))

    def render_maze(self, screen, maze=None) -> None:
        """Replay the cached wall rectangles.

        Args:
            screen: the surface to paint on.
            maze: unused; kept so existing callers keep working.  The maze
                is built in ``start_level`` now.
        """
        for rect, color in self.maze_layers:
            screen.fill(color, rect)

    def hud_height(self) -> int:
        """Pixels reserved above the maze for the score and lives."""
        return self.hud_scale() * 10 + MARGIN * 2

    def hud_scale(self) -> int:
        """Blockfont scale for the HUD, kept proportional to the window."""
        return max(3, min(6, self.width // 130))

    def maze_origin(self) -> tuple[int, int]:
        """Return the top-left pixel of the maze.

        Centred horizontally, but centred in the space *below* the HUD so a
        short maze never grows up underneath the score.
        """
        grid = self.maze_gen.maze
        cols, rows = len(grid[0]), len(grid)
        top = self.hud_height() + MARGIN
        return ((self.width - cols * self.cell_size) // 2,
                top + max(0, (self.height - top - MARGIN
                              - rows * self.cell_size) // 2))

    def fit_cell_size(self) -> int:
        """Pick the largest cell that still fits this level on screen.

        A fixed cell size makes a 14x10 level look lost in a 780x780 window
        while a 19x14 level overflows it, so the size is derived from the
        level instead.  The odd remainder goes into the walls, which keeps
        the corridor -- and therefore sprite scale -- identical everywhere.
        """
        grid = self.maze_gen.maze
        cols, rows = len(grid[0]), len(grid)
        usable_h = (self.height - self.hud_height() - 2 * MARGIN)
        room = min((self.width - 2 * MARGIN) // cols, usable_h // rows)
        return max(MIN_CELL, room - room % 2)

    def tile_to_pixel(self, tx: float, ty: float, ox: int, oy: int,
                      size: int) -> tuple[int, int]:
        """Convert a core tile position into a pixel position for a sprite.

        The core walks a ``(2w+1)`` x ``(2h+1)`` grid of *tiles* while the
        renderer draws *cells*: cell ``(cx, cy)`` is tile ``(2cx+1, 2cy+1)``,
        so a tile maps back to a cell at ``(t - 1) / 2``.  A half-tile
        position is a passage tile, and it lands on the gap between two
        cells, which is exactly where the corridor carries on.

        Args:
            tx, ty: tile position, fractional while an entity is moving.
            ox, oy: maze origin, from ``maze_origin``.
            size: sprite scale.

        Returns:
            Pixel position of the sprite's top-left corner.
        """
        sprite = 7 * size
        return (round(ox + (tx - 1) / 2 * self.cell_size
                      + (self.cell_size - sprite) / 2),
                round(oy + (ty - 1) / 2 * self.cell_size
                      + (self.cell_size - sprite) / 2))

    def start_level(self, index: int) -> None:
        """Build the core model and the drawing data for level *index*.

        Both sides generate the same maze from the same size and seed, so
        the walls drawn from ``maze_gen`` and the tiles the model walks
        always describe one maze.  Only the resolution differs, and
        ``tile_to_pixel`` bridges it.

        Args:
            index: 0-based level index into the configured levels.

        Raises:
            IndexError: *index* is past the last configured level.
        """
        self.current_level = index
        spec = self.levels[index]
        self.mw, self.mh = spec.width, spec.height
        self.maze_gen = _generate(self.mw, self.mh, self.seed)
        self.maze_width = self.maze_gen._width
        self.maze_height = self.maze_gen._height
        self.cell_size = self.fit_cell_size()
        thickness = max(2, round(self.cell_size * 0.13))
        corridor = self.cell_size - 2 * thickness
        self.band_size = [thickness, corridor, thickness]
        self.band_offset = [0, thickness, thickness + corridor]
        self.maze_cells = self._populate_cells()
        self.build_maze_layers()
        self.playfield = Playfield(spec, index + 1, self.config)
        self.points = self.playfield.score
        self.popups = []

    def centre_of(self, tx: float, ty: float) -> tuple[int, int]:
        """Pixel centre of the sprite standing on core tile ``(tx, ty)``."""
        ox, oy = self.maze_origin()
        return (round(ox + (tx - 1) / 2 * self.cell_size + self.cell_size / 2),
                round(oy + (ty - 1) / 2 * self.cell_size + self.cell_size / 2))

    def draw_pellets(self, screen) -> None:
        """Draw every pellet the core still has, from the core's own sets.

        The model owns what is left to eat, so the drawing follows the
        model rather than keeping a second copy that can disagree.

        Power pellets breathe on a slow sine so they read as the one thing
        on the board worth going out of your way for.  The period is long
        and the radius barely moves, because this is ambience: the player
        is watching the next corridor, not the corners.
        """
        if self.playfield is None:
            return
        field = self.playfield.level
        ox, oy = self.maze_origin()
        size = self.entity_size()
        small_r = max(1.5, size * 0.11)
        body, halo = self.colors["pellet"], shade(self.colors["pellet"], 0.5)
        breath = 0.5 + 0.5 * math.sin(2 * math.pi * self.anim
                                      / self.PELLET_PERIOD)
        big_r = size * (0.21 + 0.035 * breath)
        for tx, ty in sorted(field.pacgums):
            cx, cy = self.centre_of(tx, ty)
            self.stamp_pellet(screen, cx, cy, small_r, body)
        for tx, ty in sorted(field.super_pacgums):
            cx, cy = self.centre_of(tx, ty)
            self.stamp_pellet(screen, cx, cy, big_r + 1.5, halo)
            self.stamp_pellet(screen, cx, cy, big_r, body)

    def stamp_pellet(self, screen, cx: int, cy: int, radius: float,
                     color: tuple) -> None:
        """Stamp one pellet as horizontal runs, the way the board does.

        Deliberately not :func:`~pacman.ui.figures.disc`: a pellet solved
        as a true circle comes out smooth and reads as a bubble, where
        the run-length version keeps the chunky stepped edge that says
        "arcade" at a glance.
        """
        for dy, span in self.pellet_stamp(radius):
            screen.fill(color, (cx - span, cy + dy, 2 * span + 1, 1))

    def pellet_stamp(self, radius: float) -> list:
        """Scanline half-widths of a pellet of *radius*, memoised.

        Every pellet on the board is the same size, so the circle is solved
        once per radius rather than once per pellet per frame.
        """
        key = round(radius, 2)
        stamp = self.stamps.get(key)
        if stamp is None:
            reach = int(math.ceil(radius))
            stamp = [(dy, int(round(math.sqrt(max(
                0.0, radius * radius - dy * dy)))))
                for dy in range(-reach, reach + 1)]
            stamp = [(dy, span) for dy, span in stamp if span >= 0.5]
            self.stamps[key] = stamp
        return stamp

    def draw_player_from_core(self, screen) -> None:
        """Draw the player where the core model currently is.

        The mouth cycles while the player is actually travelling and rests
        shut when they are not, so the sprite reports the model's state
        instead of just decorating it.  The cycle is a triangle wave, which
        gives one linear open and one linear close with no easing to tune,
        and it never gates input -- movement stays exactly as fast as the
        core says it is.
        """
        if self.playfield is None:
            return
        player = self.playfield.player
        moving = player.direction is not None
        if moving:
            phase = (self.anim % self.CHOMP_PERIOD) / self.CHOMP_PERIOD
            mouth = 1.0 - abs(2.0 * phase - 1.0)
        else:
            mouth = 0.0
        pacman(screen, *self.centre_of(player.x, player.y),
               self.entity_size() / 2, self.colors["yellow"],
               facing_of(player), mouth)

    def draw_ghosts_from_core(self, screen) -> None:
        """Draw the four ghosts, with eyes on their heading.

        An edible ghost flashes between blue and white on a fixed period,
        the universal "eat me now" signal, and every ghost's skirt waves on
        the same slow beat so the board feels alive without the sprites
        drawing attention away from the corridors.
        """
        if self.playfield is None:
            return
        phase = int(self.anim / self.GHOST_PERIOD) % 2
        flash = int(self.anim / self.FRIGHT_FLASH) % 2 == 0
        for spirit, color_name in zip(self.playfield.ghosts, GHOST_COLORS):
            if spirit.is_edible:
                color = self.colors["blue"] if flash else self.colors["white"]
                # The white half of the flash is a solid silhouette, so the
                # face has to flip to dark or the ghost reads as a blob.
                face = self.colors["white"] if flash else self.colors["wall_core"]
            else:
                color = self.colors[color_name]
                face = self.colors["white"]
            ghost(screen, *self.centre_of(spirit.x, spirit.y),
                  self.entity_size() / 2, color,
                  facing_of(spirit), phase,
                  scared=spirit.is_edible, face=face)

    def draw_popups(self, screen) -> None:
        """Draw and retire the floating score rewards."""
        for popup in list(self.popups):
            left = popup["life"] / popup["span"]
            # ease-out: fast off the pellet, settling as it fades, so the
            # number reads clearly at the moment it appears.
            rise = (1.0 - left) ** 2
            y = popup["y"] - round(rise * popup["rise"])
            fade = 0.35 + 0.65 * left
            self.write(popup["text"], screen, popup["x"], y,
                       self.popup_scale(), shade(popup["color"], fade))
            popup["life"] -= self.dt
            if popup["life"] <= 0:
                self.popups.remove(popup)

    def popup_scale(self) -> int:
        """Blockfont scale for score popups."""
        return max(2, self.hud_scale() - 1)

    def draw_hud(self, screen) -> None:
        """Draw the score, the level and the remaining lives.

        Lives are drawn as little Pac-Men rather than the word "LIVES":
        the icon is read pre-attentively, so a glance at the corner is
        enough to know how many are left without counting digits.
        """
        if self.playfield is None:
            return
        scale = self.hud_scale()
        pad = MARGIN
        label = shade(self.colors["cyan"], 0.62)
        value = self.colors["white"]
        self.write("SCORE", screen, pad, pad, scale, label)
        self.write(f"{self.points:06d}", screen,
                   pad + self.text_width("SCORE", scale) + scale * 3, pad,
                   scale, value)
        right = self.width - pad - self.text_width("LIVES", scale)
        self.write("LIVES", screen, right, pad, scale, label)
        icon = scale * 3
        for i in range(max(0, self.playfield.player.lives)):
            pacman(screen, right - (i + 1) * (icon + scale * 2),
                   pad + scale * 3, icon / 2, self.colors["yellow"],
                   (1.0, 0.0), 0.85)

    def save_player(self, name: str, points: int) -> None:
        import json

        try:
            with open("players.json", "r") as file:
                players = json.load(file)
                if players.get(name, False):
                    players[name]["score"] += points
                else:
                    players[name] = {}
                    players[name]["score"] = points
            with open("players.json", "w") as file:
                json.dump(players, file, indent=2)
        except json.JSONDecodeError:
            Logger.error("Invalid JSON in players data ...")
            os._exit(1)
        except FileNotFoundError as error:
            Logger.error(f"File {error.filename} not found ...")
            os._exit(1)

    def game_loop(self, screen, dt: float) -> None:
        """Advance the core model by *dt* seconds and draw the result.

        Every rule -- movement, turning, eating, frightening, being caught
        -- belongs to the core.  This method only steps it and paints what
        it now says, so there is exactly one model of the game.

        Args:
            screen: the pygame surface to draw on.
            dt: seconds since the previous frame.
        """
        if self.playfield is None:
            return
        self.anim += dt
        self.dt = dt
        was = [spirit.state for spirit in self.playfield.ghosts]
        self.playfield.update(dt)
        for spirit, state in zip(self.playfield.ghosts, was):
            if state != GhostState.EATEN and spirit.state == GhostState.EATEN:
                self.reward_ghost(spirit)
        self.points = self.playfield.score
        self.draw_frame(screen)

    def reward_ghost(self, spirit) -> None:
        """Float the ghost's score up from where it was eaten."""
        self.popups.append({
            "x": self.centre_of(spirit.x, spirit.y)[0] - self.popup_span() // 2,
            "y": self.centre_of(spirit.x, spirit.y)[1] - self.popup_scale() * 4,
            "text": str(self.config.points_per_ghost),
            "color": self.colors["cyan"],
            "life": 0.85,
            "span": 0.85,
            "rise": self.cell_size * 0.9,
        })

    def popup_span(self) -> int:
        """Pixel width of the widest score popup."""
        return self.text_width(str(self.config.points_per_ghost), self.popup_scale())

    def draw_frame(self, screen) -> None:
        """Paint one whole frame: maze, pellets, player, ghosts, HUD."""
        self.clear(screen)
        self.render_maze(screen, self.code_to_walls(self.maze_gen.maze))
        self.draw_pellets(screen)
        self.draw_player_from_core(screen)
        self.draw_ghosts_from_core(screen)
        self.draw_hud(screen)
        self.draw_popups(screen)

    def toggle_cheat(self, index: int) -> bool:
        """Toggle the cheat at *index* and push the effect into the core.

        The menu only ever flipped a dict; the rules live in the model, so
        the change is handed to the ``Playfield`` here rather than being
        re-implemented on this side.

        Args:
            index: position in ``cheat_options``.

        Returns:
            True for EXIT, meaning the cheat menu should close.
        """
        name = self.cheat_options[index]
        if name == "EXIT":
            Logger.log(name)
            return True
        on = not self.cheats_activated[name]
        self.cheats_activated[name] = on
        if self.playfield is None:
            return False
        if name == "INVICIBILITY":
            self.playfield.set_invincible(on)
        elif name == "FREEZE GHOSTS":
            self.playfield.set_ghosts_frozen(on)
        elif name == "2x SPEED":
            self.playfield.set_double_speed(on)
        elif name == "SKIP LEVEL" and on:
            self.next_level()
        return False

    def handle_end_of_level(self, screen) -> bool:
        """React to the core reporting the level or the run is over.

        Args:
            screen: the pygame surface to redraw on.

        Returns:
            True when the run has ended and the caller should stop playing.
        """
        if self.playfield is None:
            return False
        if self.playfield.game_over:
            self.clear(screen)
            self.game_over(screen)
            return True
        if self.playfield.level_cleared:
            if self.current_level + 1 >= len(self.levels):
                self.clear(screen)
                self.winner_screen(screen)
                return True
            self.next_level()
        return False

    def clear(self, screen) -> None:
        """Fill the window with the background colour."""
        screen.fill(self.colors["void"])

    def next_level(self) -> None:
        """Advance to the next level, rebuilding the core model with it.

        Raises:
            IndexError: there is no level after the current one.
        """
        self.start_level(self.current_level + 1)

    def draw_line(self, screen, text, y, size, color,
                  palette=None) -> None:
        """Draw *text* centred horizontally at row *y*.

        The size shrinks until the line fits the window.  Laying text out
        at a fixed size is how the end-of-run prompt ended up 1024px wide
        on a 780px screen, running off both edges and unreadable; measuring
        here means no call site has to remember to.

        Args:
            text: the line to draw; every character must be in the font.
            y: top row in pixels.
            size: requested glyph scale, reduced if the line overflows.
            color: colour for a single-colour line.
            palette: when given, cycles through it per character instead
                of using *color*.
        """
        step = self.LETTER_W * size + 2
        while size > 1 and len(text) * step > self.width - 2 * MARGIN:
            size -= 1
            step = self.LETTER_W * size + 2
        x = (self.width - len(text) * step) // 2
        for i, char in enumerate(text):
            self.write_char(char, screen, size, x, y,
                            color if palette is None
                            else palette[i % len(palette)])
            x += step

    def winner_screen(self, screen) -> None:
        """Every level cleared: a coin, a rainbow line, and the way out."""
        size = self.TEXT_SIZE + 2
        glyph_width = len(self.chars["$"][0]) * size
        self.write_char("$", screen, size,
                        self.width // 2 - glyph_width // 2,
                        self.height // 10, self.colors["yellow"])

        self.draw_line(screen, "CONGRATULATIONS - YOU WON!",
                       self.height // 2, size, None,
                       palette=list(self.colors.values()))
        self.draw_line(screen, "Press space to go to the menu...",
                       self.height // 2 + 100, self.TEXT_SIZE,
                       self.colors["white"])

    def game_over(self, screen) -> None:
        """The run ended: red, centred, with the way out spelled out."""
        self.draw_line(screen, "GAME OVER", self.height // 2,
                       self.TEXT_SIZE + 2, self.colors["red"])
        self.draw_line(screen, "Press space to go to the menu...",
                       self.height // 2 + 70, self.TEXT_SIZE,
                       self.colors["red"])

    def run(self) -> None:

        # ponytail: only display is needed (no mixer/font).  pygame.init()
        # would open ALSA on machines with no sound card, blocking ~30s in C
        # where SIGINT cannot be handled.  Add modules here only if used.
        pygame.display.init()
        screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.flip()

        running = True
        playing = False
        reading_name = False
        # Initialised with the rest of the loop state: reading_name is only
        # ever set where name is assigned, but relying on that made flake8
        # (rightly) think the name screen could read an unbound name.
        name = ""
        # Set once a run starts, so the score is banked exactly once when
        # it ends.  It used to be saved when the name was typed, while the
        # score was still 0, and the q key saved a literal 0 -- so scores
        # never reached players.json at all.
        banked = False
        at_home_page = True
        on_pause = False
        cheat_on = False
        pressed_first_cheat = False

        pause_idx = 0
        menu_idx = 0
        cheat_idx = 0
        menu_option = pause_idx % 2
        cheat_option = cheat_idx % 5
        selected = menu_idx % len(self.menu_options)

        self.show_menu(screen, menu_idx)
        last = time.perf_counter()

        while running:
            now = time.perf_counter()
            dt = now - last
            last = now
            if (playing is True and on_pause is not True
                    and cheat_on is not True and self.playfield is not None):
                self.game_loop(screen, dt)
                if self.handle_end_of_level(screen):
                    playing = False
                    if not banked:
                        self.save_player(name, self.points)
                        banked = True
            for event in pygame.event.get():
                at_home_page = True

                if event.type == pygame.KEYDOWN:
                    if reading_name:
                        if not playing and at_home_page and event.key == pygame.K_LEFT:
                            selected = menu_idx % len(self.menu_options)
                            self.clear(screen)
                            self.show_menu(screen, selected)
                            reading_name = False
                        if event.key == pygame.K_RETURN:
                            if self.valid_name(name):
                                self.start_level(0)
                                banked = False
                                self.draw_frame(screen)
                                playing = True
                                reading_name = False
                        elif event.key == pygame.K_BACKSPACE:
                            name = name[:-1]
                            self.set_player_name(screen, name)
                        else:
                            ch = self.key_chars.get(event.key)
                            if ch and len(name) < 10:
                                if ch.isalpha() and event.mod & (pygame.KMOD_SHIFT | pygame.KMOD_CAPS):
                                    ch = ch.upper()
                                elif ch == "-" and event.mod & pygame.KMOD_SHIFT:
                                    ch = "_"
                                name += ch
                                self.set_player_name(screen, name)
                        continue

                    if event.key == pygame.K_q:
                        # Quitting mid-run still counts: bank the score so
                        # it is not thrown away, once and only once.
                        if playing and name and not banked:
                            self.save_player(name, self.points)
                            banked = True
                        running = False

                    elif event.key == pygame.K_DOWN and not playing:
                        menu_idx += 1
                        selected = menu_idx % len(self.menu_options)
                        self.clear(screen)
                        self.show_menu(screen, selected)

                    elif event.key == pygame.K_UP and not playing:
                        menu_idx -= 1
                        selected = menu_idx % len(self.menu_options)
                        self.clear(screen)
                        self.show_menu(screen, selected)

                    elif event.key == pygame.K_RETURN and playing is not True:
                        if self.menu_options[selected] == "Exit":
                            running = False

                        if self.menu_options[selected] == "Play":
                            name = ""
                            reading_name = True
                            self.set_player_name(screen, name)
                            at_home_page = False

                        if self.menu_options[selected] == "View Highscores":
                            self.clear(screen)
                            self.show_highscores(screen)

                        if self.menu_options[selected] == "Instructions":
                            self.clear(screen)
                            self.show_instructions(screen)

                    elif not playing and at_home_page and event.key == pygame.K_LEFT:
                        selected = menu_idx % len(self.menu_options)
                        self.clear(screen)
                        self.show_menu(screen, selected)

                    elif playing is True:
                        if cheat_on is True:
                            if event.key == pygame.K_RETURN:
                                if self.toggle_cheat(cheat_option):
                                    cheat_on = False
                                else:
                                    self.clear(screen)
                                    self.cheat_menu(screen, cheat_option)

                            if event.key == pygame.K_UP:
                                cheat_idx -= 1
                                cheat_option = cheat_idx % 5
                                self.clear(screen)
                                self.cheat_menu(screen, cheat_option)
                            if event.key == pygame.K_DOWN:
                                cheat_idx += 1
                                cheat_option = cheat_idx % 5
                                self.clear(screen)
                                self.cheat_menu(screen, cheat_option)
                        if pressed_first_cheat is False and event.key == pygame.K_4 and cheat_on is not True:
                            pressed_first_cheat = True
                        elif pressed_first_cheat is True and event.key == pygame.K_2:
                            pressed_first_cheat = False
                            cheat_on = True
                            cheat_option = cheat_idx % 5
                            self.clear(screen)
                            self.cheat_menu(screen, cheat_option)
                        elif pressed_first_cheat is True and event.key != pygame.K_2:
                            pressed_first_cheat = False
                        if on_pause is True and not cheat_on:
                            if event.key == pygame.K_UP:
                                pause_idx -= 1
                                menu_option = pause_idx % 2
                                self.clear(screen)
                                self.pause_menu(screen, menu_option)
                            if event.key == pygame.K_DOWN:
                                pause_idx += 1
                                menu_option = pause_idx % 2
                                self.clear(screen)
                                self.pause_menu(screen, menu_option)
                        if event.key == pygame.K_RETURN and on_pause is True and menu_option == 0:
                            on_pause = False
                        elif event.key == pygame.K_RETURN and on_pause is True and menu_option == 1:
                            self.current_level = 0
                            self.clear(screen)
                            self.show_menu(screen, 0)
                            on_pause = False
                            playing = False
                            self.playfield = None
                        elif event.key == pygame.K_ESCAPE:
                            self.clear(screen)
                            self.pause_menu(screen, menu_option)
                            on_pause = not on_pause

                        if event.key == pygame.K_r:
                            self.start_level(self.current_level)
                            self.draw_frame(screen)
                            playing = True
                        if event.key == pygame.K_n and self.current_level < len(self.levels) - 1:
                            self.next_level()
                            self.draw_frame(screen)
                            playing = True

                        if self.current_level == len(self.levels) and event.key == pygame.K_SPACE:
                            self.current_level = 0
                            self.clear(screen)
                            self.show_menu(screen, 0)
                            on_pause = False
                            playing = False
                            self.playfield = None

                        # Steering is a request, not a move: the core holds it
                        # until the tile it wants is reachable, so a key held
                        # into a wall turns as soon as the opening appears.
                        # No wall test happens here -- core owns the grid.
                        wanted = KEY_TO_DIRECTION.get(event.key)
                        if (wanted is not None and on_pause is not True
                                and cheat_on is not True
                                and self.playfield is not None):
                            self.playfield.steer(wanted)

            pygame.display.flip()
