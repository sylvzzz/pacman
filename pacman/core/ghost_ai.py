"""Ghost decision making: chase when normal, flee when frightened.

Owner: Person A
Contents: manhattan(), chase_target() per personality
  (Blinky/Pinky/Inky/Clyde), _open_directions(), _without_reversal(),
  _best_by_distance() using Level BFS maps, choose_ghost_direction().

Distances come from ``Level.distances_from``, so "closer" means closer
along the corridors, not through walls.
"""

import random

from .entities import Direction, Ghost, GhostState, Personality, Player
from .level import Level, Point

AMBUSH_LOOKAHEAD = 4
SHY_DISTANCE = 8
WHIMSICAL_RANDOM_CHANCE = 0.3
FLEE_RANDOM_CHANCE = 0.15
UNREACHABLE = 10 ** 9


def manhattan(a: Point, b: Point) -> int:
    """Return the Manhattan distance between two tiles."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def chase_target(ghost: Ghost, level: Level, player: Player) -> Point:
    """Return the tile a normal ghost tries to reach.

    Each personality aims differently so the pack surrounds the player
    instead of queueing behind it.  The whimsical randomness lives in
    ``choose_ghost_direction``; its target is the player's tile.
    """
    if ghost.personality is Personality.AMBUSHER:
        facing = player.direction
        if facing is None:
            return player.tile
        ahead = (player.tile[0] + facing.dx * AMBUSH_LOOKAHEAD,
                 player.tile[1] + facing.dy * AMBUSH_LOOKAHEAD)
        return level.nearest_open(ahead)
    if (ghost.personality is Personality.SHY
            and manhattan(ghost.tile, player.tile) <= SHY_DISTANCE):
        return ghost.home
    return player.tile


def _open_directions(ghost: Ghost, level: Level) -> list[Direction]:
    """Return the directions the ghost can take from its tile."""
    return [d for d in Direction if level.is_open(*d.step(ghost.tile))]


def _without_reversal(ghost: Ghost,
                      options: list[Direction]) -> list[Direction]:
    """Drop the U-turn unless it is the only way out (a dead end)."""
    if ghost.direction is None:
        return options
    forward = [d for d in options if d is not ghost.direction.opposite()]
    return forward or options


def _best_by_distance(ghost: Ghost, options: list[Direction],
                      distances: dict[Point, int],
                      rng: random.Random, minimise: bool) -> Direction:
    """Pick the option whose next tile is nearest (or farthest) by BFS.

    Ties are broken at random so ghosts do not all take the same
    corner.  A tile missing from *distances* counts as very far.
    """
    scores = {d: distances.get(d.step(ghost.tile), UNREACHABLE)
              for d in options}
    best = min(scores.values()) if minimise else max(scores.values())
    return rng.choice([d for d in options if scores[d] == best])


def choose_ghost_direction(ghost: Ghost, level: Level, player: Player,
                           rng: random.Random,
                           scatter: bool = False) -> Direction | None:
    """Decide where *ghost* goes from the tile it is standing on.

    Args:
        ghost: the deciding ghost, at a tile centre.
        level: the maze, providing BFS distance maps.
        player: the player to chase or flee from.
        rng: random source for tie-breaks and whims.
        scatter: True during a scatter phase: a normal ghost heads for
            its home corner instead of chasing, which gives the player
            breathing room.

    Returns:
        A direction into an open tile, or None when the ghost stays
        (EATEN, or walled in).
    """
    if ghost.state is GhostState.EATEN:
        return None
    options = _without_reversal(ghost, _open_directions(ghost, level))
    if not options:
        return None
    if ghost.state is GhostState.FRIGHTENED:
        if rng.random() < FLEE_RANDOM_CHANCE:
            return rng.choice(options)
        distances = level.distances_from(player.tile)
        return _best_by_distance(ghost, options, distances, rng, False)
    if (ghost.personality is Personality.WHIMSICAL
            and rng.random() < WHIMSICAL_RANDOM_CHANCE):
        return rng.choice(options)
    if scatter:
        distances = level.distances_from(ghost.home)
        return _best_by_distance(ghost, options, distances, rng, True)
    distances = level.distances_from(chase_target(ghost, level, player))
    return _best_by_distance(ghost, options, distances, rng, True)
