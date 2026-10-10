"""Drawing code restricted to pygame calls that exist in MLX.

Owner: Person B
Planned contents: Canvas (pixel-buffer access, hand-rasterised
  rects/circles/text), Renderer (owns the window; draws menu, pages, maze image
  cached per level, entities, HUD, pause and end panels).
"""
from pacman.ui.blockfont import Character
from pacman.ui.maze import Wall
from pacman.ui.highscores import HighscoreEntry
from pacman.ui.figures import (CreatureType, facing_of, ghost,
                               pacman, shade)
from pacman.core.config import GameConfig
from pacman.core.entities import Direction, Ghost, GhostState
from pacman.core.game import Game, Phase
from pacman.core.level import Level
from pacman.core.maze_loader import _generate
import math
import random
from pathlib import Path
from typing import Any

import pygame

# Arrow keys onto the core's directions.  The two enums disagree on
# purpose -- the core counts tiles the way the model reads them (UP is
# -y), the UI counts them the way a compass does -- so the translation
# lives in one table instead of being re-derived at each call site.
# Seed for the home menu's decorative scatter.  Any fixed number works;
# it just has to be a constant, or the wallpaper changes between runs.
MENU_DECOR_SEED = 20240
#: Pellets scattered per free band on the home menu.
MENU_DECOR_PELLETS = 14

# The arcade's frightened ghost: a blue body with a peach face, and in the
# other half of the flash a white body with a red face.  Kept out of
# ``Screen.colors`` because the winner screen cycles through that dict as
# its rainbow.
FRIGHT_BLUE = (33, 33, 222)
FACE_PEACH = (255, 184, 174)
FACE_RED = (255, 0, 0)

Color = tuple[int, int, int]

# Ghost names in the core's order: Blinky, Pinky, Inky, Clyde.
GHOST_COLORS = ("blinky", "pinky", "inky", "clyde")

# Flat body colours of the four ghosts.  Kept apart from ``Screen.colors``
# so the winner screen's rainbow and the HUD reds are not affected.
GHOST_RGB = {
    "blinky": (255, 0, 0),
    "pinky": (255, 105, 180),
    "inky": (0, 255, 255),
    "clyde": (255, 128, 0),
}

KEY_TO_DIRECTION = {
    "up": Direction.UP,
    "down": Direction.DOWN,
    "left": Direction.LEFT,
    "right": Direction.RIGHT,
    "w": Direction.UP,
    "s": Direction.DOWN,
    "a": Direction.LEFT,
    "d": Direction.RIGHT,
}

# The key that opens the cheat menu, and the key of each row in it, in
# the same order as ``Screen.cheat_options``.
CHEAT_MENU_KEY = "c"
CHEAT_KEYS = ("l", "i", "s", "f", "g", "n", "t")

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
    """Draws game state onto a pygame surface.

    The screen owns no game state. It reads a ``Game`` and paints it (maze,
    pellets, entities, HUD, menus) while the scenes decide what to show.

    Attributes:
        config: the parsed configuration in use.
        width: window width in pixels.
        height: window height in pixels.
    """

    def __init__(self, config: GameConfig) -> None:
        """Set up the window size and the colouring tables.

        Args:
            config: parsed configuration, source of the window size and the
                point values shown in the HUD.
        """
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
        self.GHOST_PERIOD = 0.42
        self.FRIGHT_FLASH = 0.26
        # Seconds of flashing before a frightened ghost turns back.
        self.FRIGHT_WARNING = 2.0
        # How long the player's death animation plays, in seconds.
        self.DEATH_TIME = 1.2
        self.death_left = 0.0
        # Best score on the table, shown in the header; set by the app.
        self.high_score = 0
        self.high_score = 0
        self.death_pos = (0.0, 0.0)
        self.death_facing = (1.0, 0.0)

        # Create a simple 20x20 maze
        self.current_level = 0
        self.cheat_options = ["MORE LIVES", "INVINCIBILITY", "2x SPEED",
                              "FREEZE GHOSTS", "SCARE GHOSTS",
                              "SKIP LEVEL", "+30s"]
        self.levels = config.levels
        self.seed = config.seed
        self.mw, self.mh = (self.levels[self.current_level].width,
                            self.levels[self.current_level].height)
        self.maze_gen = _generate(self.mw, self.mh, self.seed)
        self.maze_cells = self._populate_cells()

        # The core game for the run in progress.  None until a game
        # starts; the menu does not need one.
        self.game: Game | None = None
        # The core level the maze layers were built for, so a level change
        # inside ``Game`` (it advances by itself) is noticed and redrawn.
        self._shown_level: Level | None = None
        # Per-level drawing caches, rebuilt when the level changes.
        self._maze_surface: tuple[list[Any], pygame.Surface] | None = None
        self._origin_cache: tuple[tuple[int, int],
                                  tuple[int, int]] | None = None
        self.points = 0
        # Drives every sprite animation from one monotonic clock, so the
        # mouth and the skirt stay in step and can never drift apart or
        # restart on their own.
        self.anim = 0.0
        self.dt = 0.0
        self.popups: list[dict[str, Any]] = []
        self.stamps: dict[float, list[Any]] = {}

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
        self._decor: tuple[list[Any], list[Any]] | None = None
        # ON/OFF state of every row in the cheat menu, keyed by option.
        # ON means the cheat's key is unlocked while playing.
        self.cheats_activated = dict.fromkeys(self.cheat_options, False)

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

    def write_char(self, char: str, screen: pygame.Surface, size: int,
                   x: int, y: int, color: Color = (255, 255, 0)) -> None:
        """Draw one glyph at ``(x, y)`` as solid blocks.

        Args:
            char: character to draw; unknown glyphs render as a space.
            screen: target surface.
            size: side length in pixels of a single glyph pixel.
            x: left edge in pixels.
            y: top edge in pixels.
            color: fill colour.
        """
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
        """Return the pixel width of ``text`` drawn at ``size``.

        Args:
            text: string to measure.
            size: glyph scale in pixels.
            tracking: gap in pixels between consecutive glyphs.

        Returns:
            Width in pixels, including the gaps between glyphs.
        """
        return len(text) * self.LETTER_W * size + (len(text) - 1) * tracking

    def text_height(self, texts: list[str], size: int) -> int:
        """Return the pixel height of ``texts`` drawn at ``size``.

        Args:
            texts: lines to measure; the height covers the line spacing
                between them added to one glyph height.
            size: glyph scale in pixels.

        Returns:
            Height in pixels.
        """
        return (len(texts) - 1) * self.LINE_SPACING + self.LETTER_H * size

    def write(self, text: str, screen: pygame.Surface, x: int, y: int,
              size: int, color: Color = (255, 255, 0),
              tracking: int = 5) -> None:
        """Draw *text* with its top-left at ``(x, y)``.

        Args:
            tracking: extra pixels between glyphs.  Opening the tracking up
                on a title is what separates a heading from a label without
                needing a second font, which MLX does not have.
        """
        for ch in text:
            self.write_char(ch, screen, size, x, y, color)
            x += self.LETTER_W * size + tracking

    def hline(self, screen: pygame.Surface, x: int, y: int, w: int,
              color: Color,
              thickness: int = 2) -> None:
        """Draw a horizontal rule, used to separate a title from its list."""
        if w > 0:
            screen.fill(color, (x, y, w, thickness))

    def draw_panel(self, screen: pygame.Surface, title: str,
                   items: list[str], selected: int, hint: str = "",
                   colors: list[Color] | None = None,
                   suffixes: list[tuple[str, Color]] | None = None
                   ) -> None:
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
            suffixes: optional ``(text, colour)`` per row, drawn just after
                the label.  Used for the cheat toggles, whose state has to
                read as part of the option it belongs to.
        """
        scale = self.hud_scale()
        title_scale = max(3, scale + 1)
        item_scale = max(2, scale - 1)
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
            tail = suffixes[i][0] if suffixes is not None else ""
            tail_color = suffixes[i][1] if suffixes is not None else color
            # Centre the label and its state as one unit.  A right-aligned
            # state column read as a separate table, which is why the cheat
            # options looked off-centre: the toggle belongs to its option.
            tail_w = self.text_width(tail, item_scale) if tail else 0
            gap = scale * 3 if tail else 0
            label_w = self.text_width(text, item_scale)
            x = (self.width - label_w - tail_w - gap) // 2
            if chosen:
                # The marker is its own glyph in its own colour, in the
                # gutter left of the label, so the labels stay aligned and
                # the cursor reads as chrome rather than as part of a word.
                self.write("*", screen, x - item_scale * 7, y, item_scale,
                           self.colors["cyan"])
            self.write(text, screen, x, y, item_scale, color)
            if tail:
                self.write(tail, screen, x + label_w + gap, y, item_scale,
                           tail_color)
            y += self.LETTER_H * item_scale + scale * 3

        if hint:
            # draw_line, not write: the controls line is the widest thing
            # on the panel and used to run off both edges of the window.
            self.draw_line(screen, hint, self.height - scale * 11, scale,
                           self.colors["slate"])

    def menu_bands(self, radius: int) -> tuple[Any, ...]:
        """Return the two ``(low, high)`` bands the home panel leaves empty.

        Same vertical arithmetic as ``draw_panel``, so the decoration can
        never land on the title or a row.  Inset by the ghost sprite's
        full height (``2 * radius``, the sprite is a square) rather than
        its radius: centring it in a band that only clears the radius
        drops its feet on the title.
        ``test_menu_decor_lands_only_in_the_gutters`` is what catches it
        if the panel layout ever moves.
        """
        scale = self.hud_scale()
        top = max(scale * 4, self.height // 6)
        rows = top + self.LETTER_H * (scale + 3) + scale * 7
        rows += len(self.menu_options) * (self.LETTER_H * (scale + 1)
                                          + scale * 3)
        tall = radius * 2
        return ((tall, top - tall),
                (rows + tall, self.height - scale * 13 - tall))

    def menu_decor(self) -> tuple[list[Any], list[Any]]:
        """Pick the home menu's ghost and pellet scatter, once per process.

        The window is split into four quadrants and each one gets exactly
        one ghost, at a random spot inside the free part of that quadrant
        (the panel in the middle is never touched), in ``GHOST_COLORS``
        order: upper right, upper left, lower left, lower right.  Pellets
        are spread over the two free bands and are kept clear of the
        ghosts so nothing overlaps.  Rolled once from a fixed seed and
        reused: the panel repaints on every key press, so new positions
        each time would make the screen boil.

        Returns:
            ``(ghosts, pellets)`` where a ghost is
            ``(x, y, facing, colour_name)`` and a pellet is
            ``(x, y, radius)``.
        """
        if self._decor is None:
            rng = random.Random(MENU_DECOR_SEED)
            scale = self.hud_scale()
            radius = scale * 4
            pad = scale * 7
            half = self.width // 2
            top_band, bottom_band = self.menu_bands(radius)
            left = (pad + radius, half - radius)
            right = (half + radius, self.width - pad - radius)
            quadrants = ((right, top_band), (left, top_band),
                         (left, bottom_band), (right, bottom_band))

            ghosts = []
            for color, (xs, ys) in zip(GHOST_COLORS, quadrants):
                ghosts.append((
                    rng.randint(xs[0], max(xs[0], xs[1])),
                    rng.randint(ys[0], max(ys[0], ys[1])),
                    # Pupils dead-centre: the menu ghosts pose for the
                    # player the way the arcade title art does, not look
                    # off in four different directions.
                    (0, 0),
                    color))

            span = self.width - 2 * pad
            slot = span / MENU_DECOR_PELLETS
            pellets = []
            # Even slots with a jitter inside each, not a free draw per
            # pellet: uniform randoms clump, and a bald patch reads as a
            # mistake where an even spread reads as scattered.  A pellet
            # that lands on a ghost is re-rolled a few times, then dropped.
            for low, high in self.menu_bands(scale // 2):
                for i in range(MENU_DECOR_PELLETS):
                    big = rng.random() < 0.22
                    size = scale if big else scale // 2
                    for _ in range(6):
                        x = round(pad + slot * (i + rng.uniform(0.2, 0.8)))
                        y = rng.randint(low, max(low, high))
                        if all(max(abs(x - gx), abs(y - gy))
                               > radius + size + 4
                               for gx, gy, _, _ in ghosts):
                            pellets.append((x, y, size))
                            break
            self._decor = (ghosts, pellets)
        return self._decor

    def draw_menu_decor(self, screen: pygame.Surface) -> None:
        """Draw the four ghosts and the scattered pellets round the menu."""
        ghosts, pellets = self.menu_decor()
        radius = self.hud_scale() * 4
        body = self.colors["pellet"]
        halo = shade(body, 0.5)
        unit = max(1, (2 * radius) // 14)
        for x, y, facing, color in ghosts:
            ghost(screen, x, y, radius, GHOST_RGB[color], facing,
                  pixel=unit)
        power = self.hud_scale()
        for x, y, size in pellets:
            if size == power:
                self.stamp_pellet(screen, x, y, size + 1.5, halo)
            self.stamp_pellet(screen, x, y, size, body)

    def show_menu(self, screen: pygame.Surface, selected: int = -1) -> None:
        """Draw the main menu over whatever is already on screen."""
        self.draw_menu_decor(screen)
        self.draw_panel(screen, "PAC-MAN", self.menu_options, selected,
                        "ARROWS MOVE    ENTER SELECT    Q QUIT")

    def pause_menu(self, screen: pygame.Surface,
                   selected: int = -1) -> None:
        """Draw the pause overlay."""
        self.draw_panel(screen, "PAUSED", ["Resume", "Main Menu"], selected,
                        "ESC RESUME")

    def cheat_menu(self, screen: pygame.Surface,
                   selected: int = -1) -> None:
        """Draw the cheat list with each option's ON/OFF state.

        ON means the cheat's key is unlocked while playing.  *selected*
        is the highlight the arrows move; enter arms or disarms the row
        it is on, and the row's own letter runs the cheat from anywhere.
        """
        suffixes = []
        for name in self.cheat_options:
            on = self.cheats_activated[name]
            suffixes.append(("ON" if on else "OFF", self.colors["green"]
                             if on else self.colors["red"]))
        self.draw_panel(screen, "CHEATS", self.cheat_options, selected,
                        "ARROWS MOVE    ENTER ARM    C BACK", None,
                        suffixes)

    def instruction_lines(self) -> list[str]:
        """Return the lines of ``instructions.txt``.

        Looked up in the working directory first, then next to the
        package, so a packaged build still finds it.  A missing file is
        reported on the page itself instead of stopping the game.
        """
        for folder in (Path.cwd(), Path(__file__).resolve().parents[2]):
            try:
                text = (folder / "instructions.txt").read_text(
                    encoding="utf-8")
            except OSError:
                continue
            return [line.strip() for line in text.splitlines()]
        return ["instructions.txt was not found."]

    def show_instructions(self, screen: pygame.Surface) -> None:
        """Draw the how-to-play page."""
        lines = self.instruction_lines()
        scale = self.hud_scale()
        title = "HOW TO PLAY"
        tracking = scale * 2
        title_scale = scale + 3
        top = max(scale * 4, self.height // 6)

        # Shrink the body until the whole file fits above the bottom edge.
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
            # draw_line shrinks a line to fit the window width.
            self.draw_line(screen, line, y, size, self.colors["slate"])
            y += spacing

    def show_highscores(self, screen: pygame.Surface,
                        entries: list[HighscoreEntry]) -> None:
        """Draw the top-10 table, best first.

        Args:
            screen: the surface to draw on.
            entries: the table rows, already sorted by the table.
        """
        title = "Top 10 Highest Scores"
        rows = [f"{rank}  -  {entry.name}  -  {entry.score}"
                for rank, entry in enumerate(entries, start=1)]
        if not rows:
            rows = ["No scores yet"]
        start_y = (self.height
                   - self.text_height(rows, self.TEXT_SIZE)) // 2
        self.draw_line(screen, title, start_y - self.LINE_SPACING,
                       self.TEXT_SIZE + 2, self.colors["gold"])
        start_y += 30
        # The podium reads first, the rest recedes (never darker than
        # slate: anything dimmer is unreadable on this background).
        medals = {1: self.colors["gold"], 2: self.colors["white"],
                  3: self.colors["yellow"]}
        for rank, text in enumerate(rows, start=1):
            self.draw_line(screen, text, start_y + rank * self.LINE_SPACING,
                           self.TEXT_SIZE,
                           medals.get(rank, self.colors["slate"]))

    def code_to_walls(self, raw_maze: list[list[int]]) -> list[list[Wall]]:
        """Wrap every cell code of the maze in a ``Wall``."""
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
                        inner = (x + t, y + t, w - 2 * t, h - 2 * t)
                        self.maze_layers.append((inner, core))

    def entity_size(self) -> int:
        """Diameter in pixels of the player, a ghost or a power pellet.

        Derived from the corridor rather than fixed, so an entity keeps the
        same presence-to-corridor ratio on a 14x10 level and a 19x14 one
        instead of shrinking out of sight on the bigger boards.
        """
        corridor = self.cell_size - 2 * self.band_size[0]
        return max(10, round(corridor * 0.74))

    def sprite_unit(self) -> int:
        """Side in pixels of one cell of the 14x14 ghost bitmap.

        A whole number, so every cell of the sprite is the same size and
        the ghost stays on a rigid pixel grid.  Never so large that the
        14-cell sprite would be wider than the corridor.
        """
        corridor = self.cell_size - 2 * self.band_size[0]
        return max(1, min(round(self.entity_size() / 14), corridor // 14))

    def sprite_diameter(self) -> int:
        """Pixel side of the ghost, and the diameter of the player."""
        return 14 * self.sprite_unit()

    def halo_pad(self) -> int:
        """How far a wall's glow spreads, in pixels."""
        return max(1, round(self.cell_size * 0.055))

    def core_thickness(self) -> int:
        """Thickness of the lit line inside a wall band, in pixels."""
        return max(1, round(self.cell_size * 0.045))

    def render_maze(self, screen: pygame.Surface, maze: Any = None) -> None:
        """Replay the cached wall rectangles.

        Args:
            screen: the surface to paint on.
            maze: unused; kept so existing callers keep working.  The maze
                is built in ``sync_level`` now.
        """
        cached = self._maze_surface
        if cached is None or cached[0] is not self.maze_layers:
            # The walls only change with the level, so paint them once
            # onto a window-sized surface and blit it every frame instead
            # of replaying hundreds of rectangles.
            image = pygame.Surface((self.width, self.height))
            image.fill(self.colors["void"])
            for rect, color in self.maze_layers:
                image.fill(color, rect)
            cached = (self.maze_layers, image)
            self._maze_surface = cached
        screen.blit(cached[1], (0, 0))

    def hud_height(self) -> int:
        """Pixels reserved above the maze for the score row."""
        scale = self.play_scale()
        return scale * (2 * self.LETTER_H + 3) + MARGIN * 2

    def footer_height(self) -> int:
        """Pixels reserved below the maze for the lives and the level."""
        return self.play_scale() * (self.LETTER_H + 3) + MARGIN

    def play_scale(self) -> int:
        """Blockfont scale for the in-game HUD, kept small and quiet.

        Half the menu scale, like the arcade's thin header, and never so
        wide that "HIGH SCORE" and "TIME" would touch their neighbours.
        """
        scale = max(2, self.hud_scale() // 2)
        while scale > 1:
            need = (self.text_width("SCORE", scale, scale)
                    + self.text_width("HIGH SCORE", scale, scale)
                    + self.text_width("TIME", scale, scale) + scale * 8)
            if need <= self.width - 2 * MARGIN:
                break
            scale -= 1
        return scale

    def hud_scale(self) -> int:
        """Blockfont scale for the HUD, kept proportional to the window."""
        return max(3, min(6, self.width // 130))

    def maze_origin(self) -> tuple[int, int]:
        """Return the top-left pixel of the maze.

        Centred horizontally, but centred in the space *below* the HUD so a
        short maze never grows up underneath the score.
        """
        key = (id(self.maze_gen), self.cell_size)
        if self._origin_cache is not None and self._origin_cache[0] == key:
            return self._origin_cache[1]
        grid = self.maze_gen.maze
        cols, rows = len(grid[0]), len(grid)
        top = self.hud_height() + MARGIN
        origin = ((self.width - cols * self.cell_size) // 2,
                  top + max(0, (self.height - top - self.footer_height()
                                - rows * self.cell_size) // 2))
        self._origin_cache = (key, origin)
        return origin

    def fit_cell_size(self) -> int:
        """Pick the largest cell that still fits this level on screen.

        A fixed cell size makes a 14x10 level look lost in a 780x780 window
        while a 19x14 level overflows it, so the size is derived from the
        level instead.  The odd remainder goes into the walls, which keeps
        the corridor -- and therefore sprite scale -- identical everywhere.
        """
        grid = self.maze_gen.maze
        cols, rows = len(grid[0]), len(grid)
        usable_h = (self.height - self.hud_height() - self.footer_height()
                    - MARGIN)
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

    def start_game(self) -> None:
        """Begin a new run: a fresh core ``Game`` from level 1.

        Raises:
            pacman.core.errors.MazeGenerationError: the first maze cannot
                be built.
        """
        self.game = Game(self.config)
        self.death_left = 0.0
        self.cheats_activated = dict.fromkeys(self.cheats_activated, False)
        self.sync_level()

    def restart_game(self) -> None:
        """Restart the run in progress from level 1 with a fresh score."""
        if self.game is None:
            return
        self.game.start()
        self.death_left = 0.0
        self.cheats_activated = dict.fromkeys(self.cheats_activated, False)
        self.sync_level()

    def sync_level(self) -> None:
        """Rebuild the drawing data for the level the core is now on.

        The walls are drawn from the same maze the model walks: the core
        level carries the seed it was built from (levels after the first
        use a random one), so the maze is regenerated from *that* seed
        and the two always describe one maze.  ``tile_to_pixel`` bridges
        the tile and cell resolutions.
        """
        game = self.game
        if game is None:
            return
        level = game.level
        spec = self.levels[game.level_index]
        self.current_level = game.level_index
        self.mw, self.mh = spec.width, spec.height
        self.maze_gen = _generate(self.mw, self.mh, level.seed)
        self.maze_width = self.maze_gen._width
        self.maze_height = self.maze_gen._height
        self.cell_size = self.fit_cell_size()
        thickness = max(2, round(self.cell_size * 0.13))
        corridor = self.cell_size - 2 * thickness
        self.band_size = [thickness, corridor, thickness]
        self.band_offset = [0, thickness, thickness + corridor]
        self.maze_cells = self._populate_cells()
        self.build_maze_layers()
        self._shown_level = level
        self.points = game.score
        self.popups = []

    def centre_of(self, tx: float, ty: float) -> tuple[int, int]:
        """Pixel centre of the sprite standing on core tile ``(tx, ty)``."""
        ox, oy = self.maze_origin()
        return (round(ox + (tx - 1) / 2 * self.cell_size + self.cell_size / 2),
                round(oy + (ty - 1) / 2 * self.cell_size + self.cell_size / 2))

    def draw_pellets(self, screen: pygame.Surface) -> None:
        """Draw every pellet the core still has, from the core's own sets.

        The model owns what is left to eat, so the drawing follows the
        model rather than keeping a second copy that can disagree.

        Power pellets have a fixed size: they are told apart from plain
        pellets by their radius and halo alone, with no animation.
        """
        if self.game is None:
            return
        field = self.game.level
        size = self.entity_size()
        small_r = max(1.5, size * 0.11)
        body, halo = self.colors["pellet"], shade(self.colors["pellet"], 0.5)
        big_r = size * 0.23
        for tx, ty in sorted(field.pacgums):
            cx, cy = self.centre_of(tx, ty)
            self.stamp_pellet(screen, cx, cy, small_r, body)
        for tx, ty in sorted(field.super_pacgums):
            cx, cy = self.centre_of(tx, ty)
            self.stamp_pellet(screen, cx, cy, big_r + 1.5, halo)
            self.stamp_pellet(screen, cx, cy, big_r, body)

    def stamp_pellet(self, screen: pygame.Surface, cx: int, cy: int,
                     radius: float,
                     color: Color) -> None:
        """Stamp one pellet as horizontal runs, the way the board does.

        Deliberately not :func:`~pacman.ui.figures.disc`: a pellet solved
        as a true circle comes out smooth and reads as a bubble, where
        the run-length version keeps the chunky stepped edge that says
        "arcade" at a glance.
        """
        for dy, span in self.pellet_stamp(radius):
            screen.fill(color, (cx - span, cy + dy, 2 * span + 1, 1))

    def pellet_stamp(self, radius: float) -> list[Any]:
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

    def draw_player_from_core(self, screen: pygame.Surface) -> None:
        """Draw the player where the core model currently is.

        The mouth cycles while the player is actually travelling and rests
        shut when they are not, so the sprite reports the model's state
        instead of just decorating it.  The cycle is a triangle wave, which
        gives one linear open and one linear close with no easing to tune,
        and it never gates input -- movement stays exactly as fast as the
        core says it is.
        """
        if self.game is None:
            return
        player = self.game.player
        if self.death_left > 0:
            progress = 1.0 - self.death_left / self.DEATH_TIME
            pacman(screen, *self.centre_of(*self.death_pos),
                   self.sprite_diameter() / 2, self.colors["yellow"],
                   (0.0, -1.0), min(1.95, 1.0 + progress))
            return
        moving = player.direction is not None
        if moving:
            phase = (self.anim % self.CHOMP_PERIOD) / self.CHOMP_PERIOD
            mouth = 1.0 - abs(2.0 * phase - 1.0)
        else:
            mouth = 0.0
        pacman(screen, *self.centre_of(player.x, player.y),
               self.sprite_diameter() / 2, self.colors["yellow"],
               facing_of(player), mouth)

    def draw_ghosts_from_core(self, screen: pygame.Surface) -> None:
        """Draw the four ghosts the way the arcade does.

        A hunting ghost is its own colour with white eyes looking along its
        heading.  An edible ghost flashes between a blue body with a peach
        face and a white body with a red face, the universal "eat me now"
        signal.  An eaten ghost is not drawn at all: it disappears and
        reappears when it respawns.  Every
        ghost's skirt waves on the same slow beat so the board feels alive
        without the sprites drawing attention away from the corridors.
        """
        if self.game is None or self.death_left > 0:
            return
        phase = int(self.anim / self.GHOST_PERIOD) % 2
        flash = int(self.anim / self.FRIGHT_FLASH) % 2 == 0
        unit = self.sprite_unit()
        radius = self.sprite_diameter() / 2
        for spirit, color_name in zip(self.game.ghosts, GHOST_COLORS):
            if spirit.state is GhostState.EATEN:
                continue            # eaten: gone until it respawns
            cx, cy = self.centre_of(spirit.x, spirit.y)
            if spirit.is_edible:
                warn = spirit.frightened_timer < self.FRIGHT_WARNING
                lit = flash or not warn
                color = FRIGHT_BLUE if lit else self.colors["white"]
                face = FACE_PEACH if lit else FACE_RED
                ghost(screen, cx, cy, radius, color, facing_of(spirit),
                      phase, scared=True, face=face, pixel=unit)
            else:
                ghost(screen, cx, cy, radius, GHOST_RGB[color_name],
                      facing_of(spirit), phase, pixel=unit)

    def draw_popups(self, screen: pygame.Surface) -> None:
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

    def draw_hud(self, screen: pygame.Surface) -> None:
        """Draw the arcade-style header and footer, small and quiet.

        Header: ``SCORE`` over the score on the left, ``HIGH SCORE`` in the
        middle, ``TIME`` on the right, each label over its number the way
        the arcade stacks them.  Footer: one little Pac-Man per life on
        the left, the level on the right.  The ``SCORE`` blinks, as it does
        in the arcade, and the clock turns red for the last ten seconds.
        """
        if self.game is None:
            return
        scale = self.play_scale()
        track = scale
        pad = MARGIN
        label = self.colors["white"]
        value = self.colors["white"]
        row = self.LETTER_H * scale + scale * 2

        def field(text: str, number: str, left: int, tint: Color) -> None:
            """Draw *text* over *number*, centred on each other at *left*."""
            width = max(self.text_width(text, scale, track),
                        self.text_width(number, scale, track))
            for line, y, color in ((text, pad, label),
                                   (number, pad + row, tint)):
                self.write(line, screen,
                           left + (width - self.text_width(line, scale,
                                                           track)) // 2,
                           y, scale, color, track)

        blink = int(self.anim * 2) % 2 == 0
        field("SCORE" if blink else "   ", f"{self.points:05d}", pad, value)
        best = max(self.high_score, self.points)
        centre = self.text_width("HIGH SCORE", scale, track)
        field("HIGH SCORE", f"{best:05d}", (self.width - centre) // 2, value)
        seconds = max(0, int(self.game.time_left))
        urgent = seconds <= 10 and int(self.anim * 4) % 2 == 0
        clock_w = self.text_width("TIME", scale, track)
        field("TIME", f"{seconds:03d}", self.width - pad - clock_w,
              self.colors["red"] if urgent else value)

        # Footer: lives on the left, level on the right.
        foot = self.height - self.footer_height() + scale * 2
        icon = scale * 4
        for i in range(max(0, self.game.lives)):
            pacman(screen, pad + icon // 2 + i * (icon + scale * 2),
                   foot + icon // 2 - scale, icon / 2,
                   self.colors["yellow"], (-1.0, 0.0), 0.85)
        level = f"LEVEL {self.game.level.number:02d}"
        self.write(level, screen,
                   self.width - pad - self.text_width(level, scale, track),
                   foot, scale, self.colors["slate"], track)

    def step_game(self, dt: float) -> None:
        """Advance the core game by *dt* seconds.

        Every rule -- movement, turning, eating, frightening, being caught
        -- belongs to the core.  This only steps it and keeps the
        animation clock, the level drawing and the popups in step.

        Args:
            dt: seconds since the previous frame.
        """
        if self.game is None:
            return
        self.anim += dt
        self.dt = dt
        if self.death_left > 0:
            self.death_left -= dt
            return
        was = [spirit.state for spirit in self.game.ghosts]
        lives = self.game.lives
        px, py = self.game.player.x, self.game.player.y
        self.game.update(dt)
        if self.game.lives < lives:
            self.death_left = self.DEATH_TIME
            self.death_pos = (px, py)
        if self.game.level is not self._shown_level:
            self.sync_level()
        for spirit, state in zip(self.game.ghosts, was):
            if state != GhostState.EATEN and spirit.state == GhostState.EATEN:
                self.reward_ghost(spirit)
        self.points = self.game.score

    def reward_ghost(self, spirit: Ghost) -> None:
        """Float the ghost's score up from where it was eaten."""
        cx, cy = self.centre_of(spirit.x, spirit.y)
        self.popups.append({
            "x": cx - self.popup_span() // 2,
            "y": cy - self.popup_scale() * 4,
            "text": str(self.config.points_per_ghost),
            "color": self.colors["cyan"],
            "life": 0.85,
            "span": 0.85,
            "rise": self.cell_size * 0.9,
        })

    def popup_span(self) -> int:
        """Pixel width of the widest score popup."""
        return self.text_width(str(self.config.points_per_ghost),
                               self.popup_scale())

    def draw_frame(self, screen: pygame.Surface) -> None:
        """Paint one whole frame: maze, pellets, player, ghosts, HUD."""
        self.clear(screen)
        self.render_maze(screen, self.code_to_walls(self.maze_gen.maze))
        self.draw_pellets(screen)
        self.draw_player_from_core(screen)
        self.draw_ghosts_from_core(screen)
        self.draw_hud(screen)
        self.draw_popups(screen)
        self.draw_banner(screen)

    def draw_banner(self, screen: pygame.Surface) -> None:
        """Announce the phases where play is frozen: READY and level won."""
        if self.game is None:
            return
        text = {Phase.READY: "READY!",
                Phase.LEVEL_WON: "LEVEL COMPLETED"}.get(self.game.phase)
        color = self.colors["yellow"]
        if self.death_left > 0:
            text, color = "OUCH!", self.colors["red"]
        if text is None:
            return
        size = self.TEXT_SIZE + 2
        step = self.LETTER_W * size + 2
        width = len(text) * step + size * 6
        height = self.LETTER_H * size + size * 4
        y = self.height // 2 - height // 2
        # A solid plate keeps the words legible over the maze, the way
        # the arcade blanks the area under READY!.
        screen.fill(self.colors["void"],
                    ((self.width - width) // 2, y, width, height))
        self.draw_line(screen, text, y + size * 2, size, color)

    def toggle_cheat(self, index: int) -> None:
        """Arm or disarm the key of the cheat at *index* (Enter/click).

        This only flips the ON/OFF state shown in the menu; the cheat
        itself runs from its own letter while the row is ON.  The first
        arm of a run turns the core's master switch on; a config with
        ``cheats_enabled`` false leaves ``Game`` ignoring all of it, so
        no row lights up.

        Args:
            index: position in ``cheat_options``.
        """
        game = self.game
        if game is None:
            return
        if not game.cheats.active:
            game.toggle_cheats()
        if not game.cheats.active:
            return          # cheats disabled in the config
        name = self.cheat_options[index]
        self.cheats_activated[name] = not self.cheats_activated[name]

    def steer(self, key: str) -> bool:
        """Turn an arrow key into a buffered turn for the player.

        The core keeps the request until the tile it wants is reachable,
        so a key pressed early is taken at the next junction.  No wall
        test happens here: the core owns the grid.

        Returns:
            True when *key* was an arrow key.
        """
        wanted = KEY_TO_DIRECTION.get(key)
        if wanted is None:
            return False
        if self.game is not None:
            self.game.set_direction(wanted)
        return True

    def cheat_key(self, key: str) -> int | None:
        """Run the cheat bound to *key*, if its row is armed (ON).

        The scene asks for the row back so the menu highlight can follow
        a letter pressed from anywhere in the list.

        Args:
            key: one of ``CHEAT_KEYS``.

        Returns:
            The row index of *key*, or None when it is not a cheat key
            or the row is still OFF.
        """
        key = key.lower()          # aceita "L" com Shift/CapsLock
        if key not in CHEAT_KEYS:
            return None
        index = CHEAT_KEYS.index(key)
        name = self.cheat_options[index]
        game = self.game
        if game is None or not self.cheats_activated[name]:
            return None
        if not game.cheats.active:
            game.toggle_cheats()
        if not game.cheats.active:
            return None          # cheats disabled in the config
        actions = {
            "MORE LIVES": game.add_life,
            "INVINCIBILITY": game.toggle_invincible,
            "2x SPEED": game.toggle_fast_player,
            "FREEZE GHOSTS": game.toggle_freeze_ghosts,
            "SCARE GHOSTS": game.frighten_ghosts,
            "SKIP LEVEL": game.skip_level,
            "+30s": game.add_time,
        }
        actions[name]()
        return index

    def clear(self, screen: pygame.Surface) -> None:
        """Fill the window with the background colour."""
        screen.fill(self.colors["void"])

    def draw_line(self, screen: pygame.Surface, text: str, y: int,
                  size: int, color: Color | None,
                  palette: list[Color] | None = None) -> None:
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
            if palette is not None:
                tint = palette[i % len(palette)]
            else:
                tint = color if color is not None else self.colors["white"]
            self.write_char(char, screen, size, x, y, tint)
            x += step

    def end_screen(self, screen: pygame.Surface, victory: bool, score: int,
                   name: str) -> None:
        """Draw the end of a run: verdict, final score and name prompt.

        Args:
            screen: the surface to draw on.
            victory: True when every level was cleared.
            score: the final score.
            name: what the player has typed so far.
        """
        size = self.TEXT_SIZE + 2
        top = self.height // 5
        if victory:
            glyph_width = len(self.chars["$"][0]) * size
            self.write_char("$", screen, size,
                            self.width // 2 - glyph_width // 2,
                            top - size * 9, self.colors["yellow"])
            self.draw_line(screen, "CONGRATULATIONS - YOU WON!", top + 50,
                           size, None, palette=list(self.colors.values()))
        else:
            self.draw_line(screen, "GAME OVER", top + 30, size,
                           self.colors["red"])
        self.draw_line(screen, f"FINAL SCORE  {score}", top + 130,
                       self.TEXT_SIZE, self.colors["white"])
        self.draw_line(screen, "Enter your name", top + 250,
                       self.TEXT_SIZE, self.colors["gold"])
        caret = name + "_" if len(name) < 10 else name
        self.draw_line(screen, caret, top + 320, self.TEXT_SIZE,
                       self.colors["cyan"])
        self.draw_line(screen, "ENTER SAVE    ESC SKIP", self.height - 60,
                       max(2, self.TEXT_SIZE - 2), self.colors["slate"])
