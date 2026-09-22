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

from dataclasses import dataclass, fields

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
    # TODO (you):
    # 1. Split text into lines -- text.splitlines() drops the line
    #    endings, which is what you want here.
    # 2. For each line: if line.lstrip() startswith any of
    #    COMMENT_PREFIXES, replace it with "", else keep it unchanged.
    #    A tuple works directly: str.startswith(COMMENT_PREFIXES).
    # 3. Join the result with "\n" and return it.
    raise NotImplementedError("strip_comments")


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
    # TODO (you):
    # 1. open(path, encoding="utf-8") inside a `with`, read the text.
    #    Catch the exceptions above one by one -- IsADirectoryError
    #    before OSError, since it is a subclass and a bare `except
    #    OSError` first would swallow it.  Re-raise each as ConfigError
    #    with its own sentence naming `path`.
    # 2. Feed the text through strip_comments().
    # 3. json.loads() it, catching json.JSONDecodeError.  Its .lineno
    #    and .msg are worth putting in the message -- that is what
    #    blanking comment lines above bought you.
    # 4. Check isinstance(data, dict).  A file holding `[1, 2]` parses
    #    fine but is not a config; raise ConfigError saying so.
    # 5. Return the dict.
    raise NotImplementedError("read_config_file")


def _pick_int(raw: dict[str, object], key: str, default: int,
              minimum: int, maximum: int) -> int:
    """Return ``raw[key]`` as an int within bounds, else *default*.

    Missing key: *default*, silently.  Wrong type: WARNING and
    *default*.  Out of range: WARNING and the nearer bound.

    Careful: ``bool`` subclasses ``int`` in Python, so
    ``isinstance(True, int)`` is True and ``"lives": true`` would
    quietly become 1 life.  Reject bools before the int check.
    """
    # TODO (you):
    # 1. If key not in raw: return default (no log -- a missing key is
    #    normal, subject V.3).
    # 2. value = raw[key].  If isinstance(value, bool) or not
    #    isinstance(value, int): log WARNING naming the key, the bad
    #    value and the default you are using, then return default.
    # 3. If value < minimum or value > maximum: log WARNING and return
    #    the bound you clamped to.
    # 4. Return value.
    raise NotImplementedError("_pick_int")


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
    # TODO (you): same shape as _pick_int, plus
    # - accept int *and* float (still rejecting bool),
    # - after the type check, reject values where not math.isfinite(v),
    # - return float(value) so the type is always float, never int.
    raise NotImplementedError("_pick_float")


def _pick_bool(raw: dict[str, object], key: str, default: bool) -> bool:
    """Return ``raw[key]`` if it is a real bool, else *default*.

    Only ``true``/``false`` are accepted.  ``"cheats_enabled": 1`` or
    ``"yes"`` gets a WARNING: guessing what a reviewer meant by a
    truthy string is how a config silently does the opposite of what
    the file says.
    """
    # TODO (you): missing -> default; not isinstance(value, bool) ->
    # WARNING + default; else the value.
    raise NotImplementedError("_pick_bool")


def _pick_filename(raw: dict[str, object], key: str,
                   default: str) -> str:
    """Return ``raw[key]`` as a usable filename, else *default*.

    Rejected, each with a WARNING: a non-string, an empty or
    whitespace-only name, a name containing NUL, and a name containing
    ``/`` or ``\\``.  The highscore file is written next to the game, so
    refusing separators keeps a typo in the config from writing
    somewhere else on disk.
    """
    # TODO (you):
    # 1. Missing -> default.
    # 2. not isinstance(value, str) -> WARNING + default.
    # 3. not value.strip() -> WARNING + default.
    # 4. "\0" in value, "/" in value or "\\" in value -> WARNING +
    #    default.
    # 5. Return value.
    raise NotImplementedError("_pick_filename")


def _level_spec_from(entry: object, index: int) -> LevelSpec | None:
    """Return one LevelSpec from a ``levels`` entry, or None if unusable.

    *index* only appears in the log message, so a reviewer editing the
    file is told *which* entry was wrong.
    """
    # TODO (you):
    # 1. If not isinstance(entry, dict): WARNING, return None.
    # 2. Pull "width" and "height".  Reuse _pick_int by passing the
    #    entry dict itself -- that is why _pick_int takes a dict and a
    #    key instead of a bare value.  Bounds: MIN_LEVEL_SIZE and
    #    MAX_LEVEL_SIZE, defaults from DEFAULT_LEVELS[0].
    # 3. Return LevelSpec(width, height).
    raise NotImplementedError("_level_spec_from")


def _pad_levels(specs: list[LevelSpec]) -> list[LevelSpec]:
    """Grow *specs* to MIN_LEVELS entries, returning a new list.

    Subject VI.7 requires at least ten levels, so a short ``levels``
    array is repaired rather than rejected.
    """
    # TODO (you):
    # 1. If len(specs) >= MIN_LEVELS: return specs unchanged.
    # 2. Log one WARNING (not one per added level) saying how many were
    #    given and how many you are padding to.
    # 3. Append copies of the last spec -- or grow it by a cell each
    #    time, your choice -- until len() == MIN_LEVELS, clamping to
    #    MAX_LEVEL_SIZE.  Document whichever you pick in the README.
    raise NotImplementedError("_pad_levels")


def _pick_levels(raw: dict[str, object]) -> tuple[LevelSpec, ...]:
    """Return the level sizes, at least MIN_LEVELS of them.

    Falls back to DEFAULT_LEVELS when the key is missing, is not a list,
    is empty, or holds nothing usable at all.
    """
    # TODO (you):
    # 1. "levels" not in raw -> return DEFAULT_LEVELS silently.
    # 2. not isinstance(value, list) -> WARNING + DEFAULT_LEVELS.
    # 3. Map _level_spec_from over the entries, dropping the Nones.
    # 4. If the result is empty -> WARNING + DEFAULT_LEVELS.
    # 5. Otherwise return tuple(_pad_levels(specs)).
    raise NotImplementedError("_pick_levels")


def _warn_unknown_keys(raw: dict[str, object]) -> None:
    """Log one INFO line per key that is not a setting (subject V.3)."""
    # TODO (you): iterate sorted(raw) so the output order is stable, and
    # log INFO for each key not in known_keys().  Sorting matters: a
    # test that asserts on the messages should not depend on dict order.
    raise NotImplementedError("_warn_unknown_keys")


def build_config(raw: dict[str, object]) -> GameConfig:
    """Return a GameConfig from *raw*, repairing anything invalid.

    Never raises.  Every bad value has already been warned about and
    replaced by the _pick_* helpers, so whatever a reviewer puts in the
    file, the game still starts.
    """
    # TODO (you):
    # 1. _warn_unknown_keys(raw).
    # 2. One _pick_* call per GameConfig field, passing the bounds.
    #    Suggested ranges -- adjust if you can justify it in the README:
    #      lives                    1 .. 99
    #      points_per_*             0 .. 100_000
    #      seed                     MIN_SEED .. MAX_SEED
    #      level_max_time         5.0 .. 3600.0
    #      frightened_time        0.5 .. 60.0
    #      ghost_respawn_time     0.5 .. 60.0
    #      ready_time             0.0 .. 10.0
    #      player_speed           0.5 .. 20.0
    #      ghost_speed            0.5 .. 20.0
    #      pacgum_density           1 .. 100   <- floor is 1, not 0: a
    #                                            density of 0 places no
    #                                            pacgums, and "all
    #                                            pacgums eaten" would
    #                                            be true on frame 1.
    #      window_width           320 .. 3840
    #      window_height          240 .. 2160
    #      fps                     10 .. 240
    # 3. Return GameConfig(...) with keyword arguments.
    raise NotImplementedError("build_config")


def load_config(path: str) -> GameConfig:
    """Read *path* and return the settings it describes.

    Raises:
        ConfigError: the file is unreadable or malformed.  Invalid
            *values* never reach here -- they are warned about and
            repaired by build_config().
    """
    # TODO (you): two lines -- read_config_file() then build_config().
    raise NotImplementedError("load_config")
