"""Level model: tile grid, pellets, spawn points and BFS distances.

Owner: Person A
Contents: Level, create_level().

``maze_loader`` gives walls and nothing else.  A wall grid is not yet a
playable level: it has no start, nothing to eat, and no home for the
ghosts.  This module turns one into the other, and is the only place
that decides *where* things go.

Three rules that are easy to get wrong and expensive to debug:

* **Nothing may sit on an unreachable tile.**  The package's closed
  "42" cells can wall off a pocket of corridor.  A pacgum in there can
  never be eaten, so ``pellets_left()`` never reaches zero and the
  level never ends.  ``prune_unreachable`` seals those tiles first.
* **No fixed coordinates.**  The maze changes every level, so tile
  (1, 1) may well be a wall.  Every placement searches for the nearest
  open tile instead of assuming one.
* **Distances follow corridors, not straight lines.**  ``ghost_ai``
  asks how far a target is *through the maze*, which is a BFS, not a
  subtraction.  They are cached because four ghosts ask every frame.
"""

import random

from .config import LevelSpec

# A tile coordinate, (x, y).  Written out often enough to deserve a name.
Point = tuple[int, int]

# Cap on the distance-map cache.  Every BFS map costs one int per open
# tile, so an uncapped cache on a large maze grows without limit.
MAX_CACHED_DISTANCE_MAPS = 512

# The four walkable directions, as (dx, dy).  No diagonals: Pac-Man
# turns at corners, it does not cut them.
STEPS = ((0, -1), (1, 0), (0, 1), (-1, 0))


class Level:
    """One playable maze with its pellets and spawn points.

    Built empty by ``__init__`` and filled by ``create_level``: the
    constructor only wraps a grid, so a test can build a Level from a
    hand-written grid without going near the maze package.

    Attributes:
        grid: ``grid[y][x]`` is True for a wall tile.
        number: 1-based level number, shown in the HUD.
        seed: the seed this maze was generated from.
        width: grid width in tiles.
        height: grid height in tiles.
        pacgums: tiles still holding a small pellet.
        super_pacgums: tiles still holding a power pellet.
        player_spawn: where the player starts and respawns.
        ghost_spawns: one home tile per ghost, at the four corners.
    """

    def __init__(self, grid: list[list[bool]], number: int,
                 seed: int) -> None:
        """Wrap *grid*; pellets and spawns stay empty until populated."""
        self.grid = grid
        self.number = number
        self.seed = seed
        self.height = len(grid)
        self.width = len(grid[0]) if grid else 0
        self.pacgums: set[Point] = set()
        self.super_pacgums: set[Point] = set()
        self.player_spawn: Point = (0, 0)
        self.ghost_spawns: list[Point] = []
        self._distance_cache: dict[Point, dict[Point, int]] = {}

    def is_open(self, x: int, y: int) -> bool:
        """Return True when tile *(x, y)* exists and is walkable.

        The bounds check lives here, once, so no caller has to remember
        it.  Anything outside the grid is not open -- that is what stops
        a ghost walking off the map.
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        return not self.grid[y][x]

    def open_tiles(self) -> list[Point]:
        """Return every walkable tile, in row order.

        Used for placing pellets and for picking spawn points.
        """
        # TODO (you): comprehension over range(height) x range(width),
        # keeping the tiles where is_open().
        raise NotImplementedError("Level.open_tiles")

    def neighbours(self, tile: Point) -> list[Point]:
        """Return the walkable tiles adjacent to *tile*.

        One BFS step.  Diagonals are excluded on purpose.
        """
        # TODO (you): for each (dx, dy) in STEPS, keep (x+dx, y+dy)
        # when is_open() says so.
        raise NotImplementedError("Level.neighbours")

    def distances_from(self, start: Point) -> dict[Point, int]:
        """Return the corridor distance from *start* to every tile.

        A breadth-first search, so distances follow corridors and walls
        are respected.  Tiles that cannot be reached are simply absent
        from the result, which is what makes this useful for pruning.

        Results are cached per *start*: the four ghosts ask for the same
        maps every frame and the maze does not move.  ``prune_unreachable``
        must clear the cache, since sealing tiles changes the answers.

        Args:
            start: the tile to measure from.

        Returns:
            A mapping of reachable tile -> number of steps from *start*.
        """
        # TODO (you):
        # 1. Return the cached map if `start` is already in it.
        # 2. BFS with collections.deque: start at distance 0, push each
        #    unvisited neighbour at distance + 1.  (Add the import.)
        # 3. Before caching, drop the cache if it already holds
        #    MAX_CACHED_DISTANCE_MAPS entries -- otherwise it grows
        #    forever on a long run.
        # 4. Cache and return.
        raise NotImplementedError("Level.distances_from")

    def nearest_open(self, target: Point) -> Point:
        """Return the walkable tile closest to *target*.

        Straight-line closeness is right here, unlike everywhere else:
        this answers "where can I actually put something, near this
        spot", before any corridor is known to connect.

        Args:
            target: the tile we would have liked to use.

        Returns:
            The nearest walkable tile, by Manhattan distance.

        Raises:
            ValueError: the maze has no walkable tile at all.
        """
        # TODO (you): min() over open_tiles() keyed on
        # abs(x - tx) + abs(y - ty); raise if there are none.
        raise NotImplementedError("Level.nearest_open")

    def prune_unreachable(self, start: Point) -> int:
        """Seal every tile that cannot be reached from *start*.

        Turns unreachable corridor into wall, so nothing is ever placed
        where the player cannot go.  Call it once, immediately after the
        player spawn is chosen and before anything is placed.

        Args:
            start: the tile everything must be reachable from.

        Returns:
            How many tiles were sealed.
        """
        # TODO (you):
        # 1. reachable = distances_from(start).
        # 2. Every open tile not in `reachable` becomes True (wall).
        # 3. Clear _distance_cache -- the maze just changed, so every
        #    cached map is now a lie.  This line is the whole reason
        #    the cache is private.
        # 4. Return the count.
        raise NotImplementedError("Level.prune_unreachable")

    def corner_tiles(self) -> list[Point]:
        """Return the four grid corners, walls included.

        The raw corners, in reading order (NW, NE, SW, SE).  Callers
        pass each through ``nearest_open`` to get a usable tile.
        """
        # TODO (you): the four (x, y) pairs from width and height.
        raise NotImplementedError("Level.corner_tiles")

    def pellets_left(self) -> int:
        """Return how many pellets of either kind are still uneaten.

        ``game`` clears the level when this reaches zero.
        """
        # TODO (you): the two set sizes.
        raise NotImplementedError("Level.pellets_left")


def create_level(spec: LevelSpec, number: int, seed: int,
                 pacgum_density: int, rng: random.Random) -> Level:
    """Generate a maze and populate it into a playable level.

    The only function ``game`` calls.  Order matters: the spawn is
    chosen, then the unreachable tiles are sealed, and only then is
    anything placed -- placing first would scatter pellets into pockets
    that the next step walls off.

    Args:
        spec: maze size in cells.
        number: 1-based level number.
        seed: passed to the maze package; must be >= 1.
        pacgum_density: percentage of eligible corridors that get a
            small pellet.
        rng: the random source for pellet placement, passed in so a
            test can seed it and get the same level twice.

    Returns:
        A ready-to-play level.

    Raises:
        MazeGenerationError: propagated from the maze adapter.
        ValueError: the maze has too few corridor tiles to place
            everything.
    """
    # TODO (you):
    # 1. grid = generate_tile_grid(spec.width, spec.height, seed).
    #    (Add the import from .maze_loader.)
    # 2. level = Level(grid, number, seed).
    # 3. Player spawn: nearest_open() to the centre of the grid.
    # 4. level.prune_unreachable(player_spawn)  <- before any placing.
    # 5. Ghost spawns and super-pacgums: nearest_open() to each of the
    #    four corner_tiles().  Guard against two corners resolving to
    #    the same tile on a tiny maze.
    # 6. Pacgums: every remaining open tile, minus the spawn and the
    #    super-pacgums, kept with probability pacgum_density / 100.
    # 7. Return the level.
    raise NotImplementedError("create_level")
