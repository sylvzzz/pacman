"""Game rules and state machine, independent from any graphics library.

Owner: Person A
Contents: Phase, Cheats, Game.

``Game`` is the only object the UI drives.  The UI calls ``start``,
``update``, ``set_direction``, ``toggle_pause`` and the cheat methods;
it only *reads* everything else (``score``, ``lives``, ``player``,
``ghosts``, ``level``...).  Nothing here imports pygame.

Three rules shape ``update``:

* **``dt`` is capped** at ``MAX_DT`` so a stalled window cannot make an
  entity cross a wall in one huge step.
* **Time is sliced** into steps of at most ``SUBSTEP`` seconds, so a
  fast player and a fast ghost heading at each other cannot swap tiles
  between two collision checks.
* **A state change ends the frame.**  Losing a life or winning a level
  stops the remaining slices: what is left of ``dt`` belongs to the
  next phase, which starts from a clean READY/WON state.
"""

import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from .config import GameConfig
from .entities import Direction, Ghost, GhostState, Personality, Player
from .errors import MazeGenerationError
from .ghost_ai import choose_ghost_direction
from .level import Level, create_level

MAX_DT = 0.1                 # longest dt accepted by update(), seconds
SUBSTEP = 0.02               # longest slice simulated at once, seconds
COLLISION_DISTANCE = 0.6     # Manhattan distance, in tiles
LEVEL_CLEAR_TIME = 1.5       # how long LEVEL_WON is shown, seconds
FRIGHTENED_SPEED_FACTOR = 0.5
RELEASE_STAGGER = 2.0        # extra seconds each ghost waits at home
LEVEL_SPEED_STEP = 0.04      # ghosts get 4% faster each level...
MAX_LEVEL_SPEED = 1.4        # ...up to this factor
# Alternating (scatter, chase) seconds; after the last pair it is chase
# for good, like the arcade.
MODE_SCHEDULE = ((7.0, 20.0), (7.0, 20.0), (5.0, 20.0), (5.0, 0.0))
CHEAT_SPEED_FACTOR = 1.8
CHEAT_TIME_BONUS = 30.0
MAX_SEED = 2 ** 31 - 1
PERSONALITIES = (Personality.CHASER, Personality.AMBUSHER,
                 Personality.WHIMSICAL, Personality.SHY)


class Phase(Enum):
    """The high-level state of a run, which decides what ``update`` does."""

    READY = "ready"          # frozen countdown before play (re)starts
    PLAYING = "playing"
    PAUSED = "paused"
    LEVEL_WON = "level_won"  # short banner before the next level
    GAME_OVER = "game_over"
    VICTORY = "victory"      # every level cleared


@dataclass
class Cheats:
    """The reviewer cheat switches.

    Attributes:
        active: master switch (key C).  While off, the others do
            nothing and are all reset.
        invincible: ghosts cannot hurt the player (F1).
        freeze_ghosts: ghosts stand still (F2).
        fast_player: the player moves faster (F3).
    """

    active: bool = False
    invincible: bool = False
    freeze_ghosts: bool = False
    fast_player: bool = False


class Game:
    """One run of the game: score, lives, the current level and entities.

    Attributes:
        config: the game settings.
        phase: current ``Phase``.
        score: points so far; it never decreases.
        level_index: 0-based index of the current level in the config
            (the HUD should show ``level.number``).
        level_count: how many levels the run has.
        time_left: seconds left on the level timer.
        cheats: the cheat switches.
        level: the current maze.
        player: the player.
        ghosts: the four ghosts, one per corner.
    """

    def __init__(self, config: GameConfig,
                 rng: random.Random | None = None) -> None:
        """Build level 1 and wait in READY for ``start``.

        Args:
            config: the validated settings.
            rng: random source for maze seeds, pellets and ghost whims;
                pass a seeded one for a reproducible run.

        Raises:
            MazeGenerationError: the first maze cannot be built.
        """
        self.config = config
        self._rng = rng if rng is not None else random.Random()
        self.level_count = len(config.levels)
        self.cheats = Cheats()
        self.mode_time = 0.0
        self.score = 0
        self.phase = Phase.READY
        self.level_index = 0
        self.time_left = config.level_max_time
        self._phase_timer = config.ready_time
        self._paused_from = Phase.PLAYING
        self._load_level(0, config.lives)

    @property
    def lives(self) -> int:
        """Return the lives the player has left."""
        return self.player.lives

    # ------------------------------------------------------------------
    # Level setup
    # ------------------------------------------------------------------

    def _seed_for(self, index: int) -> int:
        """Return the maze seed: fixed for level 1, random afterwards."""
        if index == 0:
            return max(1, self.config.seed)
        return self._rng.randint(1, MAX_SEED)

    def _load_level(self, index: int, lives: int) -> None:
        """Build level *index* with a fresh player and ghosts.

        Raises:
            MazeGenerationError: the maze could not be built.
        """
        spec = self.config.levels[index]
        try:
            level = create_level(spec, index + 1, self._seed_for(index),
                                 self.config.pacgum_density, self._rng)
        except ValueError as exc:
            raise MazeGenerationError(str(exc)) from exc
        self.level: Level = level
        self.level_index = index
        self.player = Player(level.player_spawn, self.config.player_speed,
                             lives)
        self.ghosts: list[Ghost] = [
            Ghost(home, self.config.ghost_speed,
                  PERSONALITIES[i % len(PERSONALITIES)])
            for i, home in enumerate(level.ghost_spawns)]
        self.time_left = self.config.level_max_time
        self.ghost_speed = self.config.ghost_speed * min(
            MAX_LEVEL_SPEED, 1.0 + LEVEL_SPEED_STEP * index)
        self._stagger_ghosts()

    def _stagger_ghosts(self) -> None:
        """Make the ghosts leave home one after another, and restart modes."""
        self.mode_time = 0.0
        for i, ghost in enumerate(self.ghosts):
            ghost.release_timer = i * RELEASE_STAGGER

    @property
    def scattering(self) -> bool:
        """Return True while the ghosts are in a scatter phase."""
        clock = self.mode_time
        for scatter, chase in MODE_SCHEDULE:
            if clock < scatter:
                return True
            clock -= scatter
            if clock < chase:
                return False
            clock -= chase
        return False

    def _begin_ready(self) -> None:
        """Freeze for ``ready_time``; with none configured, play now."""
        self._phase_timer = self.config.ready_time
        if self._phase_timer > 0:
            self.phase = Phase.READY
        else:
            self.phase = Phase.PLAYING

    # ------------------------------------------------------------------
    # Commands from the UI
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start (or restart) a run from level 1 with a fresh score."""
        self.score = 0
        self.cheats = Cheats()
        self._load_level(0, self.config.lives)
        self._begin_ready()

    def set_direction(self, direction: Direction) -> None:
        """Buffer a turn; the player takes it at the next open junction."""
        if self.phase in (Phase.READY, Phase.PLAYING):
            self.player.wanted = direction

    def toggle_pause(self) -> None:
        """Pause a running game, or resume a paused one."""
        if self.phase is Phase.PAUSED:
            self.phase = self._paused_from
        elif self.phase in (Phase.READY, Phase.PLAYING):
            self._paused_from = self.phase
            self.phase = Phase.PAUSED

    # ------------------------------------------------------------------
    # Cheats
    # ------------------------------------------------------------------

    def toggle_cheats(self) -> None:
        """Turn cheat mode on or off, if the config allows it.

        Turning it off also clears every switch.
        """
        if not self.config.cheats_enabled:
            return
        if self.cheats.active:
            self.cheats = Cheats()
        else:
            self.cheats.active = True

    def toggle_invincible(self) -> None:
        """F1: flip invincibility."""
        if self.cheats.active:
            self.cheats.invincible = not self.cheats.invincible

    def toggle_freeze_ghosts(self) -> None:
        """F2: flip ghost freeze."""
        if self.cheats.active:
            self.cheats.freeze_ghosts = not self.cheats.freeze_ghosts

    def toggle_fast_player(self) -> None:
        """F3: flip the speed boost."""
        if self.cheats.active:
            self.cheats.fast_player = not self.cheats.fast_player

    def add_life(self) -> None:
        """F4: give the player one more life."""
        if self.cheats.active and self.phase is not Phase.GAME_OVER:
            self.player.lives += 1

    def skip_level(self) -> None:
        """F5: win the current level immediately."""
        if self.cheats.active and self.phase is Phase.PLAYING:
            self._win_level()

    def frighten_ghosts(self) -> None:
        """F6: make every ghost edible, as a super-pacgum would."""
        if self.cheats.active and self.phase is Phase.PLAYING:
            self._frighten_all()

    def add_time(self) -> None:
        """F7: add ``CHEAT_TIME_BONUS`` seconds to the level timer."""
        if self.cheats.active and self.phase is Phase.PLAYING:
            self.time_left += CHEAT_TIME_BONUS

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the game by *dt* seconds.

        Args:
            dt: elapsed seconds since the last call; negative values
                count as 0 and values above ``MAX_DT`` are capped.
        """
        dt = min(max(dt, 0.0), MAX_DT)
        if self.phase is Phase.READY:
            self._phase_timer -= dt
            if self._phase_timer <= 0:
                self.phase = Phase.PLAYING
        elif self.phase is Phase.LEVEL_WON:
            self._phase_timer -= dt
            if self._phase_timer <= 0:
                self._load_level(self.level_index + 1, self.lives)
                self._begin_ready()
        elif self.phase is Phase.PLAYING:
            slices = max(1, math.ceil(dt / SUBSTEP))
            for _ in range(slices):
                if not self._step(dt / slices):
                    break

    def _step(self, dt: float) -> bool:
        """Simulate one short slice of play.

        Returns:
            False when something changed the run (a life lost, the
            level won) and the rest of the frame must be dropped.
        """
        self.time_left -= dt
        if self.time_left <= 0:
            self._lose_life(restart_timer=True)
            return False
        self._move_player(dt)
        if self.level.pellets_left() == 0:
            self._win_level()
            return False
        self._move_ghosts(dt)
        return self._resolve_collisions()

    def _move_player(self, dt: float) -> None:
        """Move the player and eat whatever is on the tile it reached.

        The tile eaten is the one the player is nearest to (within half
        a tile), which stays right after an instant U-turn.  ``SUBSTEP``
        keeps a slice well under half a tile, so none is ever skipped.
        """
        speed = self.config.player_speed
        if self.cheats.fast_player:
            speed *= CHEAT_SPEED_FACTOR
        self.player.speed = speed
        self.player.update(dt, self.level)
        tile = self.player.nearest_tile
        if tile in self.level.pacgums:
            self.level.pacgums.discard(tile)
            self.score += self.config.points_per_pacgum
        elif tile in self.level.super_pacgums:
            self.level.super_pacgums.discard(tile)
            self.score += self.config.points_per_super_pacgum
            self._frighten_all()

    def _frighten_all(self) -> None:
        """Make every ghost edible for ``frightened_time`` seconds."""
        for ghost in self.ghosts:
            ghost.frighten(self.config.frightened_time)

    def _move_ghosts(self, dt: float) -> None:
        """Run the ghost timers, then move each ghost unless frozen."""
        self.mode_time += dt
        for ghost in self.ghosts:
            ghost.tick(dt)
            if self.cheats.freeze_ghosts or ghost.release_timer > 0:
                continue
            ghost.speed = self.ghost_speed
            if ghost.state is GhostState.FRIGHTENED:
                ghost.speed *= FRIGHTENED_SPEED_FACTOR
            ghost.advance(dt, self.level, self._picker(ghost))

    def _picker(self, ghost: Ghost) -> Callable[[], Direction | None]:
        """Return the callback asking the AI where *ghost* goes next."""
        return lambda: choose_ghost_direction(
            ghost, self.level, self.player, self._rng, self.scattering)

    def _touches(self, ghost: Ghost) -> bool:
        """Return True when *ghost* is close enough to hit the player."""
        return manhattan_f(self.player.x, self.player.y,
                           ghost.x, ghost.y) < COLLISION_DISTANCE

    def _resolve_collisions(self) -> bool:
        """Eat touched edible ghosts; a touched normal ghost costs a life.

        Returns:
            False when a life was lost, True otherwise.
        """
        hurt = False
        for ghost in self.ghosts:
            if not ghost.is_active or not self._touches(ghost):
                continue
            if ghost.is_edible:
                ghost.eat(self.config.ghost_respawn_time)
                self.score += self.config.points_per_ghost
            else:
                hurt = True
        if hurt and not self.cheats.invincible:
            self._lose_life(restart_timer=False)
            return False
        return True

    def _lose_life(self, restart_timer: bool) -> None:
        """Take a life, then end the game or respawn everyone.

        Args:
            restart_timer: refill the level timer (used for a timeout;
                dying to a ghost keeps the time already spent).
        """
        self.player.lives -= 1
        if self.player.lives <= 0:
            self.player.lives = 0
            self.phase = Phase.GAME_OVER
            return
        if restart_timer:
            self.time_left = self.config.level_max_time
        self.player.reset(self.level.player_spawn)
        for ghost, home in zip(self.ghosts, self.level.ghost_spawns):
            ghost.reset(home)
        self._stagger_ghosts()
        self._begin_ready()

    def _win_level(self) -> None:
        """Finish the level: the next one, or VICTORY after the last."""
        if self.level_index + 1 >= self.level_count:
            self.phase = Phase.VICTORY
        else:
            self.phase = Phase.LEVEL_WON
            self._phase_timer = LEVEL_CLEAR_TIME


def manhattan_f(ax: float, ay: float, bx: float, by: float) -> float:
    """Return the Manhattan distance between two float positions."""
    return abs(ax - bx) + abs(ay - by)
