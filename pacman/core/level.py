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
from collections import deque

from .config import LevelSpec
from .maze_loader import generate_tile_grid

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
        new: list[Point] = []
        for y in range(self.height):
            for x in range(self.width):
                if self.is_open(x, y):
                    new.append((x, y))
        return new

    def neighbours(self, tile: Point) -> list[Point]:
        """Return the walkable tiles adjacent to *tile*.

        One BFS step.  Diagonals are excluded on purpose.
        """
        x, y = tile
        new: list[Point] = []
        for dx, dy in STEPS:
            nx = x + dx
            ny = y + dy
            if self.is_open(nx, ny):
                new.append((nx, ny))
        return new

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
        cached = self._distance_cache.get(start)
        if cached is not None:
            return cached
        dist: dict[Point, int] = {}
        if self.is_open(*start):
            dist[start] = 0
            queue: deque[Point] = deque([start])
            while queue:
                tile = queue.popleft()
                for nxt in self.neighbours(tile):
                    if nxt not in dist:
                        dist[nxt] = dist[tile] + 1
                        queue.append(nxt)
        if len(self._distance_cache) >= MAX_CACHED_DISTANCE_MAPS:
            self._distance_cache.clear()
        self._distance_cache[start] = dist
        return dist

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
        tiles = self.open_tiles()
        if not tiles:
            raise ValueError("the maze has no walkable tile")
        tx, ty = target
        return min(tiles, key=lambda t: abs(t[0] - tx) + abs(t[1] - ty))

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
        reachable = self.distances_from(start)
        sealed = 0
        for x, y in self.open_tiles():
            if (x, y) not in reachable:
                self.grid[y][x] = True
                sealed += 1
        self._distance_cache.clear()
        return sealed

    def corner_tiles(self) -> list[Point]:
        """Return the four grid corners, walls included.

        The raw corners, in reading order (NW, NE, SW, SE).  Callers
        pass each through ``nearest_open`` to get a usable tile.
        """
        right = self.width - 1
        bottom = self.height - 1
        return [(0, 0), (right, 0), (0, bottom), (right, bottom)]

    def pellets_left(self) -> int:
        """Return how many pellets of either kind are still uneaten.

        ``game`` clears the level when this reaches zero.
        """
        return len(self.pacgums) + len(self.super_pacgums)


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
    grid = generate_tile_grid(spec.width, spec.height, seed)
    level = Level(grid, number, seed)
    level.player_spawn = level.nearest_open(
        (level.width // 2, level.height // 2))
    level.prune_unreachable(level.player_spawn)

    tiles = level.open_tiles()
    if len(tiles) < 5:
        raise ValueError(
            f"maze has only {len(tiles)} corridor tiles, need at least 5")
    taken = {level.player_spawn}
    for cx, cy in level.corner_tiles():
        spot = min((t for t in tiles if t not in taken),
                   key=lambda t: abs(t[0] - cx) + abs(t[1] - cy))
        taken.add(spot)
        level.ghost_spawns.append(spot)
        level.super_pacgums.add(spot)

    for tile in tiles:
        if tile not in taken and rng.randrange(100) < pacgum_density:
            level.pacgums.add(tile)
    return level
