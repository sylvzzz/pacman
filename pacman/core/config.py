"""Configuration loading with comment support and safe defaults.

Owner: Person A
Contents: LevelSpec, GameConfig, strip_comments(), read_config_file(),
  the _pick_* clamping helpers, build_config(), load_config().

Policy, from subject V.2 and V.3:

* a missing key takes its default, silently;
* a present but invalid value logs a WARNING and is clamped to the
  nearest bound or replaced by its default;
* an unknown key logs an INFO line and is ignored;
* only an unreadable or malformed *file* raises ConfigError and stops
  the program.

So ``build_config`` never raises, and ``read_config_file`` is the only
function here that can.  The config is swapped during the defense, so
every branch above will be exercised by a reviewer.
"""
import json
import math
from dataclasses import dataclass, fields
from .errors import ConfigError
from .log import get_logger

# Imports you will need to add as you fill the bodies below, kept out
# for now so `make lint-strict` stays green on the scaffold:
#     import json                     -- read_config_file
#     import math                     -- _pick_float (math.isfinite)
#     from .errors import ConfigError -- read_config_file
#     from .log import get_logger     -- every _pick_* and the warnings

COMMENT_PREFIXES = ("#", "//")

# At least 10 levels are mandatory (subject VI.7).
MIN_LEVELS = 10

# A level needs four distinct corners plus a centre, and the assigned
# package returns a wrong-shaped grid for size (1, 1) -- it hands back a
# 2x2 maze.  Five cells per side is the smallest size that is both
# playable and safe to pass to the generator.
MIN_LEVEL_SIZE = 5

# (2 * 40 + 1) = 81 tiles per side is already more than a window shows.
MAX_LEVEL_SIZE = 40

# The package treats seed 0 as "pick a random seed", which would make
# level 1 unreproducible, so 1 is the floor.
MIN_SEED = 1
MAX_SEED = 2 ** 31 - 1


@dataclass(frozen=True)
class LevelSpec:
    """Maze size of one level, in generator cells (not tiles)."""

    width: int
    height: int


DEFAULT_LEVELS: tuple[LevelSpec, ...] = (
    LevelSpec(14, 10),
    LevelSpec(15, 10),
    LevelSpec(15, 11),
    LevelSpec(16, 11),
    LevelSpec(16, 12),
    LevelSpec(17, 12),
    LevelSpec(17, 13),
    LevelSpec(18, 13),
    LevelSpec(18, 14),
    LevelSpec(19, 14),
)


@dataclass(frozen=True)
class GameConfig:
    """Validated, immutable game settings.

    Frozen on purpose: once the file is parsed nothing may change a
    setting, so a bug cannot make the rules drift mid-game.  The field
    names are the config file keys, and both owners read this object --
    renaming a field is a contract change (see WORK_SPLIT.md).
    """

    highscore_filename: str = "highscores.json"
    lives: int = 3
    points_per_pacgum: int = 10
    points_per_super_pacgum: int = 50
    points_per_ghost: int = 200
    seed: int = 42
    level_max_time: float = 90.0
    frightened_time: float = 8.0
    ghost_respawn_time: float = 5.0
    ready_time: float = 1.5
    player_speed: float = 5.0
    ghost_speed: float = 4.0
    pacgum_density: int = 90
    cheats_enabled: bool = True
    window_width: int = 960
    window_height: int = 720
    fps: int = 60
    levels: tuple[LevelSpec, ...] = DEFAULT_LEVELS


def known_keys() -> frozenset[str]:
    """Return every config key build_config() understands.

    Derived from the dataclass instead of a hand-written list, so adding
    a setting can never desync the unknown-key check.
    """
    return frozenset(field.name for field in fields(GameConfig))


def strip_comments(text: str) -> str:
    """Return *text* with whole-line ``#`` and ``//`` comments blanked.

    A comment line becomes an empty line rather than disappearing, so
    the line numbers in json's own error messages still match the file
    the user is looking at.

    Only *whole-line* comments are stripped.  A ``#`` inside a value is
    kept, because ``{"name": "a # b"}`` is valid JSON and cutting at the
    ``#`` would corrupt it.
    """

    kept = []
    for line in text.split("\n"):
        if line.lstrip().startswith(COMMENT_PREFIXES):
            kept.append("")
        else:
            kept.append(line)
    return "\n".join(kept)


def read_config_file(path: str) -> dict[str, object]:
    """Read *path*, strip its comments and return its JSON object.

    The only function in this module that raises.  Each failure gets its
    own message, because "could not read the config" tells the user
    nothing about which of these went wrong:

    * the file does not exist            -> FileNotFoundError
    * the path is a directory            -> IsADirectoryError
    * the file cannot be opened          -> PermissionError
    * anything else the OS refuses       -> OSError
    * the bytes are not UTF-8 text       -> UnicodeDecodeError
    * the text is not valid JSON         -> json.JSONDecodeError
    * the top level is not a JSON object -> a list, string or number

    Raises:
        ConfigError: with a distinct message for each case above.
    """
    try:
        with open(path, encoding="utf-8") as config_file:
            text = config_file.read()
    except FileNotFoundError as e:
        raise ConfigError(f"config file not found: {path}") from e
    except IsADirectoryError as e:
        raise ConfigError(
            f"config path is a directory, not a file: {path}") from e
    except PermissionError as e:
        raise ConfigError(
            f"config file cannot be opened for reading: {path}") from e
    except UnicodeDecodeError as e:
        raise ConfigError(
            f"config file is not valid UTF-8 text: {path}") from e
    except OSError as e:
        raise ConfigError(f"could not read {path}: {e}") from e

    try:
        data = json.loads(strip_comments(text))
    except json.JSONDecodeError as e:
        raise ConfigError(
            f"{path} is not valid JSON: {e.msg}, line {e.lineno}"
            f" column {e.colno}") from e

    if not isinstance(data, dict):
        raise ConfigError(
            f"{path} must hold a JSON object,"
            f" found {type(data).__name__}")
    return data


def _pick_int(raw: dict[str, object], key: str, default: int,
              minimum: int, maximum: int) -> int:
    """Return ``raw[key]`` as an int within bounds, else *default*.

    Missing key: *default*, silently.  Wrong type: WARNING and
    *default*.  Out of range: WARNING and the nearer bound.

    Careful: ``bool`` subclasses ``int`` in Python, so
    ``isinstance(True, int)`` is True and ``"lives": true`` would
    quietly become 1 life.  Reject bools before the int check.
    """
    if key not in raw:
        return default
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int):
        get_logger().warning(
            f"{key}: expected a whole number, got {value!r};"
            f" using {default}")
        return default
    if value < minimum or value > maximum:
        clamped = min(maximum, max(minimum, value))
        get_logger().warning(
            f"{key}: {value} is out of range"
            f" [{minimum}, {maximum}]; using {clamped}")
        return clamped
    return value


def _pick_float(raw: dict[str, object], key: str, default: float,
                minimum: float, maximum: float) -> float:
    """Return ``raw[key]`` as a float within bounds, else *default*.

    Accepts an int too, so ``"level_max_time": 90`` works.  Rejects
    bools for the same reason as _pick_int.

    Rejects NaN and infinity via ``math.isfinite``.  This is not
    theoretical: JSON accepts ``NaN`` and ``Infinity``, and a NaN
    ``frightened_time`` would make every ``timer > 0`` comparison false
    forever, so the ghosts would stay edible for the rest of the game.
    """
    if key not in raw:
        return default
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        get_logger().warning(
            f"{key}: expected a number, got {value!r};"
            f" using {default}")
        return default
    if not math.isfinite(value):
        get_logger().warning(
            f"{key}: {value} is not a finite number;"
            f" using {default}")
        return default
    if value < minimum or value > maximum:
        clamped = min(maximum, max(minimum, value))
        get_logger().warning(
            f"{key}: {value} is out of range"
            f" [{minimum}, {maximum}]; using {clamped}")
        return float(clamped)
    return float(value)


def _pick_bool(raw: dict[str, object], key: str, default: bool) -> bool:
    """Return ``raw[key]`` if it is a real bool, else *default*.

    Only ``true``/``false`` are accepted.  ``"cheats_enabled": 1`` or
    ``"yes"`` gets a WARNING: guessing what a reviewer meant by a
    truthy string is how a config silently does the opposite of what
    the file says.
    """
    if key not in raw:
        return default
    value = raw[key]
    if not isinstance(value, bool):
        get_logger().warning(
            f"{key}: expected true or false, got {value!r};"
            f" using {default}")
        return default
    return value


def _pick_filename(raw: dict[str, object], key: str,
                   default: str) -> str:
    """Return ``raw[key]`` as a usable filename, else *default*.

    Rejected, each with a WARNING: a non-string, an empty or
    whitespace-only name, a name containing NUL, and a name containing
    ``/`` or ``\\``.  The highscore file is written next to the game, so
    refusing separators keeps a typo in the config from writing
    somewhere else on disk.
    """
    if key not in raw:
        return default
    value = raw[key]
    if not isinstance(value, str):
        get_logger().warning(
            f"{key}: expected a filename string, got {value!r};"
            f" using {default!r}")
        return default
    if not value.strip():
        get_logger().warning(
            f"{key}: the filename is empty; using {default!r}")
        return default
    if "\0" in value:
        get_logger().warning(
            f"{key}: the filename contains a NUL byte;"
            f" using {default!r}")
        return default
    if "/" in value or "\\" in value:
        get_logger().warning(
            f"{key}: {value!r} must be a plain filename, not a path;"
            f" using {default!r}")
        return default
    return value


def _level_spec_from(entry: object, index: int) -> LevelSpec | None:
    """Return one LevelSpec from a ``levels`` entry, or None if unusable.

    *index* only appears in the log message, so a reviewer editing the
    file is told *which* entry was wrong.
    """
    if not isinstance(entry, dict):
        get_logger().warning(
            f"levels[{index}]: expected an object with width and"
            f" height, got {entry!r}; ignoring this level")
        return None
    width = _pick_int(entry, "width", DEFAULT_LEVELS[0].width,
                      MIN_LEVEL_SIZE, MAX_LEVEL_SIZE)
    height = _pick_int(entry, "height", DEFAULT_LEVELS[0].height,
                       MIN_LEVEL_SIZE, MAX_LEVEL_SIZE)
    return LevelSpec(width, height)


def _pad_levels(specs: list[LevelSpec]) -> list[LevelSpec]:
    """Grow *specs* to MIN_LEVELS entries, returning a new list.

    Subject VI.7 requires at least ten levels, so a short ``levels``
    array is repaired rather than rejected.
    """
    if len(specs) >= MIN_LEVELS:
        return specs
    get_logger().warning(
        f"levels: only {len(specs)} given but at least {MIN_LEVELS}"
        f" are required; padding to {MIN_LEVELS}")
    padded = list(specs)
    while len(padded) < MIN_LEVELS:
        last = padded[-1]
        padded.append(LevelSpec(
            min(MAX_LEVEL_SIZE, last.width + 1),
            min(MAX_LEVEL_SIZE, last.height + 1)))
    return padded


def _pick_levels(raw: dict[str, object]) -> tuple[LevelSpec, ...]:
    """Return the level sizes, at least MIN_LEVELS of them.

    Falls back to DEFAULT_LEVELS when the key is missing, is not a list,
    is empty, or holds nothing usable at all.
    """
    if "levels" not in raw:
        return DEFAULT_LEVELS
    value = raw["levels"]
    if not isinstance(value, list):
        get_logger().warning(
            f"levels: expected a list of sizes, got {value!r};"
            f" using the {len(DEFAULT_LEVELS)} built-in levels")
        return DEFAULT_LEVELS
    specs = [spec for spec in (_level_spec_from(entry, index)
                               for index, entry in enumerate(value))
             if spec is not None]
    if not specs:
        get_logger().warning(
            f"levels: no usable level sizes found;"
            f" using the {len(DEFAULT_LEVELS)} built-in levels")
        return DEFAULT_LEVELS
    return tuple(_pad_levels(specs))


def _warn_unknown_keys(raw: dict[str, object]) -> None:
    """Log one INFO line per key that is not a setting (subject V.3)."""
    known = known_keys()
    # sorted() so the output order does not depend on dict insertion
    # order, which would make a test asserting on messages flaky.
    for key in sorted(raw):
        if key not in known:
            get_logger().info(f"unknown config key ignored: {key!r}")


def build_config(raw: dict[str, object]) -> GameConfig:
    """Return a GameConfig from *raw*, repairing anything invalid.

    Never raises.  Every bad value has already been warned about and
    replaced by the _pick_* helpers, so whatever a reviewer puts in the
    file, the game still starts.
    """

    _warn_unknown_keys(raw)
    defaults = GameConfig()
    return GameConfig(
        highscore_filename=_pick_filename(
            raw, "highscore_filename", defaults.highscore_filename),
        lives=_pick_int(raw, "lives", defaults.lives, 1, 99),
        points_per_pacgum=_pick_int(
            raw, "points_per_pacgum",
            defaults.points_per_pacgum, 0, 100_000),
        points_per_super_pacgum=_pick_int(
            raw, "points_per_super_pacgum",
            defaults.points_per_super_pacgum, 0, 100_000),
        points_per_ghost=_pick_int(
            raw, "points_per_ghost",
            defaults.points_per_ghost, 0, 100_000),
        seed=_pick_int(raw, "seed", defaults.seed, MIN_SEED, MAX_SEED),
        level_max_time=_pick_float(
            raw, "level_max_time", defaults.level_max_time, 5.0, 3600.0),
        frightened_time=_pick_float(
            raw, "frightened_time", defaults.frightened_time, 0.5, 60.0),
        ghost_respawn_time=_pick_float(
            raw, "ghost_respawn_time",
            defaults.ghost_respawn_time, 0.5, 60.0),
        ready_time=_pick_float(
            raw, "ready_time", defaults.ready_time, 0.0, 10.0),
        player_speed=_pick_float(
            raw, "player_speed", defaults.player_speed, 0.5, 20.0),
        ghost_speed=_pick_float(
            raw, "ghost_speed", defaults.ghost_speed, 0.5, 20.0),
        pacgum_density=_pick_int(
            raw, "pacgum_density", defaults.pacgum_density, 1, 100),
        cheats_enabled=_pick_bool(
            raw, "cheats_enabled", defaults.cheats_enabled),
        window_width=_pick_int(
            raw, "window_width", defaults.window_width, 320, 3840),
        window_height=_pick_int(
            raw, "window_height", defaults.window_height, 240, 2160),
        fps=_pick_int(raw, "fps", defaults.fps, 10, 240),
        levels=_pick_levels(raw),
    )


def load_config(path: str) -> GameConfig:
    """Read *path* and return the settings it describes.

    Raises:
        ConfigError: the file is unreadable or malformed.  Invalid
            *values* never reach here -- they are warned about and
            repaired by build_config().
    """
    return build_config(read_config_file(path))
