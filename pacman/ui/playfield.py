"""Adapter that drives the headless core on behalf of the UI.

Owner: Person B
Contents: Playfield

The core owns the model: ``create_level`` places the maze, the spawns and
the pellets, ``Player``/``Ghost`` own movement, and ``choose_ghost_direction``
owns what a ghost does next.  Nothing here re-implements a rule.  This
module only does the two jobs the core deliberately leaves to its caller:

* it owns *time* -- it converts a frame delta into ``update``/``advance``
  calls on the core objects;
* it applies the consequences the core documents but does not perform --
  eating a pellet, frightening the ghosts on a power pellet, and what
  happens when a ghost touches the player.

Keeping this in ``ui`` is what lets the core stay free of pygame: the
renderer reads plain numbers off the entities and draws them, and never
asks the model to draw anything.

One unit mismatch to keep in mind when reading the renderer: core works in
*tiles* on a ``(2w+1)`` x ``(2h+1)`` grid, while the renderer draws *cells*
on a ``w`` x ``h`` grid.  ``Screen.tile_to_pixel`` is the only place that
converts between them.
"""

import random
from functools import partial

from pacman.core.config import GameConfig, LevelSpec
from pacman.core.entities import Direction, Ghost, Player, Personality
from pacman.core.ghost_ai import choose_ghost_direction
from pacman.core.level import Level, create_level

# Arcade order: Blinky, Pinky, Inky, Clyde.  The renderer's ghost colours
# are listed in the same order so the two cannot drift apart.
GHOST_PERSONALITIES = (
    Personality.CHASER,
    Personality.AMBUSHER,
    Personality.WHIMSICAL,
    Personality.SHY,
)

GHOST_COLORS = ("red", "magenta", "orange", "cyan")

# Manhattan distance, in tiles, at which a ghost is considered to have
# touched the player.  Both entities are drawn well over half a tile wide,
# so anything less than one tile reads as a near miss.
TOUCH_DISTANCE = 0.6

# A frame longer than this is clamped.  Core's ``Mover`` walks a distance
# budget, so a long frame cannot tunnel through a wall, but clamping keeps
# a stalled window (a drag, a breakpoint) from teleporting everything.
MAX_DT = 0.1


class Playfield:
    """One level in progress: the core objects plus their consequences.

    Attributes:
        level: the core ``Level`` -- grid, pellets and spawns.
        player: the core ``Player``.
        ghosts: the four core ``Ghost`` objects, in ``GHOST_COLORS`` order.
        score: points eaten so far.
        invincible: while True a ghost cannot cost a life.
        ghosts_frozen: while True the ghosts do not move.
        level_cleared: set once every pellet is gone.
        game_over: set once the player is out of lives.
    """

    def __init__(self, spec: LevelSpec, number: int,
                 config: GameConfig) -> None:
        """Build level *number* (1-based) from *spec* and place everyone.

        Args:
            spec: maze size for this level.
            number: 1-based level number, shown in the HUD.
            config: the loaded game configuration.

        Raises:
            ValueError: the generated maze is too small to play.
            pacman.core.errors.MazeGenerationError: maze generation failed.
        """
        self.config = config
        self.number = number
        self.level: Level = create_level(
            spec, number, config.seed, config.pacgum_density,
            random.Random(config.seed))
        self.player = Player(self.level.player_spawn,
                             config.player_speed, config.lives)
        self.ghosts = [
            Ghost(home, config.ghost_speed, personality)
            for home, personality
            in zip(self.level.ghost_spawns, GHOST_PERSONALITIES)
        ]
        self.score = 0
        self.invincible = False
        self.ghosts_frozen = False
        self.level_cleared = False
        self.game_over = False
        self.base_player_speed = config.player_speed
        # Ghost randomness is kept apart from pellet placement, so changing
        # how many ghosts move can never shift the maze's contents.
        self.rng = random.Random(config.seed + 1)

    # ── input ───────────────────────────────────────────────────

    def steer(self, direction: Direction) -> None:
        """Buffer a turn request for the player.

        The core keeps the request until the tile it wants is reachable, so
        a key pressed early is taken at the next junction instead of being
        dropped.  The renderer must not pre-check walls itself: core is the
        only thing that knows where they are.

        Args:
            direction: the way the player asked to go.
        """
        self.player.wanted = direction

    # ── per frame ───────────────────────────────────────────────

    def update(self, dt: float) -> None:
        """Advance everything by *dt* seconds and apply the rules.

        Args:
            dt: elapsed seconds since the previous frame.
        """
        if self.game_over or self.level_cleared:
            return
        dt = min(dt, MAX_DT)
        self.player.update(dt, self.level)
        self._move_ghosts(dt)
        self._eat_pellets()
        self._resolve_touches()

    def _move_ghosts(self, dt: float) -> None:
        """Tick every ghost's timers and move it, unless frozen."""
        for ghost in self.ghosts:
            ghost.tick(dt)
            if self.ghosts_frozen:
                continue
            ghost.advance(dt, self.level, partial(
                choose_ghost_direction, ghost, self.level, self.player,
                self.rng))

    def _eat_pellets(self) -> None:
        """Collect whatever is under the player and score it."""
        tile = self.player.tile
        if tile in self.level.pacgums:
            self.level.pacgums.discard(tile)
            self.score += self.config.points_per_pacgum
        if tile in self.level.super_pacgums:
            self.level.super_pacgums.discard(tile)
            self.score += self.config.points_per_super_pacgum
            for ghost in self.ghosts:
                ghost.frighten(self.config.frightened_time)
        if self.level.pellets_left() == 0:
            self.level_cleared = True

    def _resolve_touches(self) -> None:
        """Apply what happens when a ghost is on top of the player."""
        for ghost in self.ghosts:
            if not self._touching(ghost):
                continue
            if ghost.is_edible:
                self.score += self.config.points_per_ghost
                ghost.eat(self.config.ghost_respawn_time)
            elif ghost.is_active and not self.invincible:
                self._lose_life()
                return

    def _touching(self, ghost: Ghost) -> bool:
        """Return True when *ghost* is close enough to catch the player.

        Measured on the interpolated positions rather than on ``tile``, so
        a ghost meeting the player halfway between two tiles still counts.
        """
        return (abs(ghost.x - self.player.x)
                + abs(ghost.y - self.player.y)) < TOUCH_DISTANCE

    def _lose_life(self) -> None:
        """Take a life, respawning everyone, or end the run."""
        self.player.lives -= 1
        if self.player.lives <= 0:
            self.game_over = True
            return
        self.player.reset(self.level.player_spawn)
        for ghost in self.ghosts:
            ghost.reset(ghost.home)

    # ── cheats ──────────────────────────────────────────────────

    def set_invincible(self, on: bool) -> None:
        """Turn the invincibility cheat on or off."""
        self.invincible = on

    def set_ghosts_frozen(self, on: bool) -> None:
        """Turn the freeze-ghosts cheat on or off."""
        self.ghosts_frozen = on

    def set_double_speed(self, on: bool) -> None:
        """Turn the double-speed cheat on or off."""
        self.player.speed = (self.base_player_speed * 2 if on
                             else self.base_player_speed)
