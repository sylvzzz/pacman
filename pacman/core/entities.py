"""Moving entities: directions, the player and the ghosts.

Owner: Person A
Contents: Direction, Mover, Player, GhostState, Personality, Ghost.

Everything that moves in the maze moves the same way, so the movement
lives in one place (``Mover``) and ``Player`` and ``Ghost`` only decide
*where to go next*.

Two rules shape the whole module:

* **An entity is always on a tile.**  It sits on ``tile``; while it
  travels, ``target`` is the next tile and ``progress`` (0 <= p < 1) is
  the fraction already covered.  The float position the renderer draws
  is interpolated from those three, so movement is smooth at any frame
  rate without the entity ever being "between" two tiles in the model.
* **Turns happen at tile centres only.**  The direction is chosen when
  the entity has just arrived on a tile, never mid-corridor.  That is
  what keeps entities inside the corridors, and why ``Game`` can cap
  ``dt`` and still not tunnel through a wall.
"""

from collections.abc import Callable
from enum import Enum

from .level import Level, Point


class Direction(Enum):
    """The four movement directions, valued as their (dx, dy) tile step.

    y grows downwards, like screen rows, so UP is ``(0, -1)``.  The
    renderer reads ``dx``/``dy`` to orient sprites and the mouth.
    """

    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    @property
    def dx(self) -> int:
        """Return the horizontal step: -1, 0 or 1."""
        return self.value[0]

    @property
    def dy(self) -> int:
        """Return the vertical step: -1, 0 or 1."""
        return self.value[1]

    def opposite(self) -> "Direction":
        """Return the reverse direction (UP <-> DOWN, LEFT <-> RIGHT).

        ``ghost_ai`` uses it to forbid U-turns.
        """
        return Direction((-self.dx, -self.dy))

    def step(self, tile: Point) -> Point:
        """Return the tile one step from *tile* in this direction."""
        return (tile[0] + self.dx, tile[1] + self.dy)


# Called at every tile centre to ask "which way now?".  ``None`` means
# "stay here".  A callback, so the same Mover serves the player (input)
# and the ghosts (AI) without knowing about either.
DirectionPicker = Callable[[], Direction | None]


class Mover:
    """An entity travelling tile to tile at ``speed`` tiles per second.

    Attributes:
        tile: the tile the entity last arrived on.
        target: the tile it is travelling to, or None when standing on
            a tile centre.
        progress: fraction of the way from ``tile`` to ``target``.
        speed: tiles per second.  Public and mutable: ``game`` raises it
            for the speed cheat and lowers it for frightened ghosts.
        direction: the last direction it moved in, kept after stopping
            so the renderer still knows where the mouth points.  None
            until the first move.
    """

    def __init__(self, tile: Point, speed: float) -> None:
        """Place the mover standing still on *tile*."""
        self.tile = tile
        self.speed = speed
        self.direction: Direction | None = None
        self.target: Point | None = None
        self.progress = 0.0

    @property
    def x(self) -> float:
        """Return the interpolated x position, in tile units."""
        if self.target is None:
            return float(self.tile[0])
        return self.tile[0] + (self.target[0] - self.tile[0]) * self.progress

    @property
    def y(self) -> float:
        """Return the interpolated y position, in tile units."""
        if self.target is None:
            return float(self.tile[1])
        return self.tile[1] + (self.target[1] - self.tile[1]) * self.progress

    def reset(self, tile: Point) -> None:
        """Teleport to *tile* and stop, forgetting any journey.

        Used for respawning after a life is lost and for a new level.
        """
        self.tile = tile
        self.direction = None
        self.target = None
        self.progress = 0.0

    def turn_around(self) -> None:
        """U-turn on the spot, mid-corridor, without moving.

        Only the pair (tile, target) is swapped and the progress
        mirrored, so the interpolated position stays exactly where it
        was.  Does nothing while standing on a tile centre.
        """
        if self.target is None or self.direction is None:
            return
        self.tile, self.target = self.target, self.tile
        self.progress = 1.0 - self.progress
        self.direction = self.direction.opposite()

    def advance(self, dt: float, level: Level,
                pick: DirectionPicker) -> None:
        """Move for *dt* seconds, calling *pick* at every tile centre.

        A long *dt* may cross several tiles, so this is a loop over a
        distance budget rather than a single step: leftover budget after
        arriving on a tile is spent on the next one.  That is also what
        makes the entity stop dead at a wall instead of overshooting.

        Args:
            dt: elapsed seconds.
            level: the maze, used to refuse a step into a wall.
            pick: asked for the next direction each time the entity is
                on a tile centre; returning None, or a direction that
                leads into a wall, stops it.
        """
        budget = self.speed * dt
        while budget > 0:
            if self.target is None:
                wanted = pick()
                if wanted is None:
                    return
                nxt = wanted.step(self.tile)
                if not level.is_open(*nxt):
                    return
                self.direction = wanted
                self.target = nxt
                self.progress = 0.0
            covered = min(1.0 - self.progress, budget)
            self.progress += covered
            budget -= covered
            if self.progress >= 1.0 - 1e-9:
                self.tile = self.target
                self.target = None
                self.progress = 0.0


class Player(Mover):
    """The player-controlled Pac-Man.

    Attributes:
        lives: lives left; ``game`` decrements it and ends the run at 0.
        wanted: the buffered turn.  A key pressed *before* a junction is
            remembered and taken when the junction arrives, instead of
            being lost: without it the game feels like it eats inputs.
    """

    def __init__(self, tile: Point, speed: float, lives: int) -> None:
        """Create the player on *tile* with *lives* lives."""
        super().__init__(tile, speed)
        self.lives = lives
        self.wanted: Direction | None = None

    def reset(self, tile: Point) -> None:
        """Respawn on *tile*, dropping any buffered turn.

        Lives are kept: losing one is ``game``'s decision.
        """
        super().reset(tile)
        self.wanted = None

    def pick_direction(self, level: Level) -> Direction | None:
        """Choose the direction to take from the current tile centre.

        Priority: the buffered turn if it is open, else keep going the
        way we were going if that is open, else stop.  The buffered turn
        is *not* cleared when blocked, so it still applies later.

        Args:
            level: the maze.

        Returns:
            The direction to move in, or None to stand still.
        """
        for way in (self.wanted, self.direction):
            if way is not None and level.is_open(*way.step(self.tile)):
                return way
        return None

    def reverse_now(self) -> None:
        """U-turn on the spot when the buffered turn is the opposite way.

        Turns are normally taken at tile centres, but a reversal is safe
        anywhere: the player is on the corridor it just came from.  Taking
        it at once, instead of at the next centre, is what makes the
        controls feel snappy.  Position does not change, only the pair
        (tile, target) is swapped and the progress mirrored.
        """
        if (self.direction is not None
                and self.wanted is self.direction.opposite()):
            self.turn_around()

    @property
    def nearest_tile(self) -> Point:
        """Return the tile the player is closest to.

        After an instant U-turn ``tile`` is no longer "the last tile
        arrived on", so what the player is standing on is decided by
        distance: the pellet there is eaten once the centre is within
        half a tile.
        """
        if self.target is not None and self.progress >= 0.5:
            return self.target
        return self.tile

    def update(self, dt: float, level: Level) -> None:
        """Advance for *dt* seconds, steering with ``pick_direction``."""
        self.reverse_now()
        self.advance(dt, level, lambda: self.pick_direction(level))


class GhostState(Enum):
    """What a ghost is doing, which decides how it moves and is drawn."""

    NORMAL = "normal"
    FRIGHTENED = "frightened"
    EATEN = "eaten"


class Personality(Enum):
    """How a ghost chases, after the arcade four.

    ``ghost_ai`` maps each to its own target rule.
    """

    CHASER = "chaser"          # Blinky: straight at the player
    AMBUSHER = "ambusher"      # Pinky: a few tiles ahead of the player
    WHIMSICAL = "whimsical"    # Inky: the player, with some randomness
    SHY = "shy"                # Clyde: the player when far, home when near


class Ghost(Mover):
    """A ghost with a home corner, a personality and a state machine.

    The states: NORMAL -> FRIGHTENED (super-pacgum) -> NORMAL (timer
    ends); FRIGHTENED -> EATEN (player touches it) -> NORMAL (the eyes
    reach home, or the respawn timer ends).  EATEN cannot be frightened
    again: a ghost already heading home is not edible twice.

    Attributes:
        home: the corner tile it starts on and returns to when eaten.
        personality: which chase rule ``ghost_ai`` uses.
        state: current ``GhostState``.
        frightened_timer: seconds of edibility left.
        respawn_timer: seconds until an eaten ghost returns on its own,
            the fallback for a trip that never reaches ``home``.
        release_timer: seconds it still waits on its home tile before
            leaving; ``game`` staggers these so the pack does not leave
            in one block.
    """

    def __init__(self, home: Point, speed: float,
                 personality: Personality) -> None:
        """Create a NORMAL ghost standing on its *home* tile."""
        super().__init__(home, speed)
        self.home = home
        self.personality = personality
        self.state = GhostState.NORMAL
        self.frightened_timer = 0.0
        self.respawn_timer = 0.0
        self.release_timer = 0.0
        self._travelling_home = False

    @property
    def is_edible(self) -> bool:
        """Return True while the player can eat this ghost."""
        return self.state is GhostState.FRIGHTENED

    @property
    def is_active(self) -> bool:
        """Return True when the ghost is on the board and can hurt.

        An eaten ghost is on its way back and touches nobody.
        """
        return self.state is not GhostState.EATEN

    def reset(self, tile: Point) -> None:
        """Send the ghost to *tile*, NORMAL, with both timers cleared."""
        super().reset(tile)
        self.state = GhostState.NORMAL
        self.frightened_timer = 0.0
        self.respawn_timer = 0.0
        self.release_timer = 0.0

    def frighten(self, duration: float) -> None:
        """Make the ghost edible for *duration* seconds.

        Ignored while EATEN.  Frightening an already frightened ghost
        restarts the timer: a second super-pacgum extends the effect.
        """
        if self.state is GhostState.EATEN:
            return
        if self.state is GhostState.NORMAL:
            self.turn_around()      # the arcade flips the pack's heading
        self.state = GhostState.FRIGHTENED
        self.frightened_timer = duration

    def eat(self, respawn_time: float) -> None:
        """Turn the ghost into eyes that walk home as EATEN.

        The ghost stays where it was eaten: ``ghost_ai`` steers the eyes
        back to ``home`` and the ghost revives standing on it.  Eaten
        *on* home there is no trip to make, so it waits for
        ``respawn_time`` instead -- an instant revival would put a live
        ghost under the player's feet.
        """
        self._travelling_home = self.tile != self.home
        self.state = GhostState.EATEN
        self.frightened_timer = 0.0
        self.respawn_timer = respawn_time

    def tick(self, dt: float) -> None:
        """Count the active timer down by *dt* and change state at zero.

        A ghost still waiting to be released counts ``release_timer``
        down as well.  FRIGHTENED counts ``frightened_timer`` and
        returns to NORMAL;
        EATEN returns to NORMAL on reaching ``home``, or when
        ``respawn_timer`` runs out; NORMAL
        does nothing.  Clamp the finished timer to 0.0.
        """
        self.release_timer = max(0.0, self.release_timer - dt)
        if self.state is GhostState.FRIGHTENED:
            self.frightened_timer -= dt
            if self.frightened_timer <= 0:
                self.frightened_timer = 0.0
                self.state = GhostState.NORMAL
        elif self.state is GhostState.EATEN:
            self.respawn_timer -= dt
            arrived = (self._travelling_home and self.tile == self.home
                       and self.target is None)
            if self.respawn_timer <= 0 or arrived:
                self.respawn_timer = 0.0
                self.state = GhostState.NORMAL
