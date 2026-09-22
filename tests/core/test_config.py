"""Tests for pacman.core.config (Person A).

These are the acceptance criteria for config.py.  Read the test name,
then make it pass.  Grouped by function, in the order you should
implement them.
"""

import json
from pathlib import Path

import pytest

from pacman.core.config import (
    DEFAULT_LEVELS,
    MAX_LEVEL_SIZE,
    MIN_LEVEL_SIZE,
    MIN_LEVELS,
    MIN_SEED,
    GameConfig,
    LevelSpec,
    build_config,
    known_keys,
    load_config,
    read_config_file,
    strip_comments,
)
from pacman.core.errors import ConfigError

from ..conftest import RecordingHandler


# --------------------------------------------------------------------
# strip_comments
# --------------------------------------------------------------------

def test_strip_comments_blanks_a_hash_line() -> None:
    """A line starting with # becomes empty."""
    assert strip_comments("# a comment\n{}") == "\n{}"


def test_strip_comments_blanks_a_slash_line() -> None:
    """C++ style comments are supported too (subject V.2)."""
    assert strip_comments("// a comment\n{}") == "\n{}"


def test_strip_comments_blanks_an_indented_comment() -> None:
    """Leading whitespace before # still marks a comment line."""
    assert strip_comments("    # indented\n{}") == "\n{}"


def test_strip_comments_preserves_line_count() -> None:
    """Line numbers must survive, so json error messages stay usable."""
    text = "# one\n# two\n{\n}\n"
    assert len(strip_comments(text).split("\n")) == len(text.split("\n"))


def test_strip_comments_keeps_a_hash_inside_a_value() -> None:
    """Only whole-line comments are stripped.

    ``{"name": "a # b"}`` is valid JSON; cutting at the # would break it.
    """
    line = '{"highscore_filename": "a # b.json"}'
    assert strip_comments(line) == line


def test_strip_comments_keeps_a_trailing_comment_untouched() -> None:
    """A # after real content is NOT a comment, by design."""
    line = '{"lives": 3}  # not stripped'
    assert strip_comments(line) == line


def test_strip_comments_on_empty_text() -> None:
    """The empty file must not crash."""
    assert strip_comments("") == ""


# --------------------------------------------------------------------
# read_config_file -- the only function here that may raise
# --------------------------------------------------------------------

def test_read_config_file_reads_an_object(tmp_path: Path) -> None:
    """A valid file with comments parses into a dict."""
    path = tmp_path / "ok.json"
    path.write_text('# comment\n{"lives": 5}\n', encoding="utf-8")
    assert read_config_file(str(path)) == {"lives": 5}


def test_read_config_file_missing_file(tmp_path: Path) -> None:
    """A missing file is a ConfigError, never a traceback."""
    with pytest.raises(ConfigError):
        read_config_file(str(tmp_path / "nope.json"))


def test_read_config_file_directory(tmp_path: Path) -> None:
    """A directory passed as the config is a ConfigError."""
    with pytest.raises(ConfigError):
        read_config_file(str(tmp_path))


def test_read_config_file_malformed_json(tmp_path: Path) -> None:
    """Broken JSON is a ConfigError."""
    path = tmp_path / "bad.json"
    path.write_text('{"lives": }', encoding="utf-8")
    with pytest.raises(ConfigError):
        read_config_file(str(path))


def test_read_config_file_empty_file(tmp_path: Path) -> None:
    """An empty file is not valid JSON."""
    path = tmp_path / "empty.json"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ConfigError):
        read_config_file(str(path))


def test_read_config_file_only_comments(tmp_path: Path) -> None:
    """A file of nothing but comments is not valid JSON either."""
    path = tmp_path / "comments.json"
    path.write_text("# just\n# comments\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        read_config_file(str(path))


def test_read_config_file_top_level_list(tmp_path: Path) -> None:
    """Valid JSON that is not an object is still not a config."""
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ConfigError):
        read_config_file(str(path))


def test_read_config_file_top_level_number(tmp_path: Path) -> None:
    """`42` parses as JSON but is not a config object."""
    path = tmp_path / "num.json"
    path.write_text("42", encoding="utf-8")
    with pytest.raises(ConfigError):
        read_config_file(str(path))


def test_read_config_file_not_utf8(tmp_path: Path) -> None:
    """Undecodable bytes are a ConfigError, not a UnicodeDecodeError."""
    path = tmp_path / "bytes.json"
    path.write_bytes(b"\xff\xfe\x00{")
    with pytest.raises(ConfigError):
        read_config_file(str(path))


def test_read_config_file_accepts_a_utf8_bom(tmp_path: Path) -> None:
    """A byte-order mark must not reject an otherwise valid config.

    Editors on Windows write a BOM by default, and a BOM is not legal
    JSON, so a plain "utf-8" read refuses a good file.
    """
    path = tmp_path / "bom.json"
    path.write_bytes(b"\xef\xbb\xbf" + b'{"lives": 5}')
    assert read_config_file(str(path)) == {"lives": 5}


def test_read_config_file_deeply_nested(tmp_path: Path) -> None:
    """Deep nesting raises RecursionError inside json, not ValueError.

    RecursionError is a RuntimeError, so the JSONDecodeError and
    ValueError clauses cannot see it.  Unhandled, it reaches the user
    as a traceback.
    """
    path = tmp_path / "deep.json"
    path.write_text("[" * 200_000, encoding="utf-8")
    with pytest.raises(ConfigError):
        read_config_file(str(path))


def test_read_config_file_deeply_nested_object(tmp_path: Path) -> None:
    """The same hole, reached through nested objects instead of arrays."""
    path = tmp_path / "deepo.json"
    path.write_text('{"a":' * 100_000 + "1" + "}" * 100_000,
                    encoding="utf-8")
    with pytest.raises(ConfigError):
        read_config_file(str(path))


def test_read_config_file_absurdly_long_number(tmp_path: Path) -> None:
    """A bare ValueError from json.loads must still be a ConfigError.

    CPython caps integer/string conversion at 4300 digits and raises a
    plain ValueError -- NOT a JSONDecodeError, which is only a subclass
    of it.  Catching the subclass does not catch the parent.
    """
    path = tmp_path / "big.json"
    path.write_text('{"seed": ' + "9" * 5000 + "}", encoding="utf-8")
    with pytest.raises(ConfigError):
        read_config_file(str(path))


def test_read_config_file_duplicate_keys_take_the_last(
    tmp_path: Path,
) -> None:
    """Documented behaviour: JSON leaves duplicates undefined.

    Python keeps the last occurrence.  Pinned here so the choice is
    deliberate rather than accidental.
    """
    path = tmp_path / "dup.json"
    path.write_text('{"lives": 3, "lives": 99}', encoding="utf-8")
    assert read_config_file(str(path)) == {"lives": 99}


def test_read_config_file_messages_are_distinct(tmp_path: Path) -> None:
    """Different failures must not share one message (style rule).

    A reviewer who sees the same sentence for a missing file and for
    broken JSON cannot tell which happened.
    """
    missing = tmp_path / "gone.json"
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")

    messages = []
    for path in (missing, broken, tmp_path):
        with pytest.raises(ConfigError) as caught:
            read_config_file(str(path))
        messages.append(str(caught.value))

    assert len(set(messages)) == len(messages)


# --------------------------------------------------------------------
# build_config -- must never raise
# --------------------------------------------------------------------

def test_build_config_empty_gives_defaults() -> None:
    """An empty config is entirely valid: every key is optional."""
    assert build_config({}) == GameConfig()


def test_build_config_reads_good_values() -> None:
    """Valid values are passed through untouched."""
    config = build_config({"lives": 5, "points_per_pacgum": 25})
    assert config.lives == 5
    assert config.points_per_pacgum == 25


def test_build_config_missing_key_is_silent(
    log_records: RecordingHandler,
) -> None:
    """A missing key takes its default without warning (subject V.3)."""
    build_config({"lives": 3})
    assert log_records.warnings == []


def test_build_config_unknown_key_logs_info(
    log_records: RecordingHandler,
) -> None:
    """An unknown key is ignored with an INFO line, not a warning."""
    config = build_config({"unicorn_mode": True})
    assert config == GameConfig()
    assert any("unicorn_mode" in line for line in log_records.infos)
    assert log_records.warnings == []


def test_build_config_wrong_type_warns_and_defaults(
    log_records: RecordingHandler,
) -> None:
    """A string where an int belongs falls back to the default."""
    config = build_config({"lives": "three"})
    assert config.lives == GameConfig().lives
    assert any("lives" in line for line in log_records.warnings)


def test_build_config_rejects_bool_for_an_int() -> None:
    """bool subclasses int: `true` must not become 1 life.

    This is the trap in isinstance(True, int) -- if you forget it, a
    config saying "lives": true starts the player on a single life.
    """
    assert build_config({"lives": True}).lives == GameConfig().lives


def test_build_config_clamps_above_maximum(
    log_records: RecordingHandler,
) -> None:
    """A huge value is clamped, with a warning."""
    config = build_config({"lives": 10 ** 9})
    assert config.lives < 10 ** 9
    assert any("lives" in line for line in log_records.warnings)


def test_build_config_clamps_below_minimum() -> None:
    """Zero lives is unplayable, so it is clamped up."""
    assert build_config({"lives": 0}).lives >= 1


def test_build_config_clamps_negative_values() -> None:
    """Negative lives is clamped, not accepted."""
    assert build_config({"lives": -5}).lives >= 1


def test_build_config_seed_zero_is_clamped() -> None:
    """The package reads seed 0 as "random", which breaks level 1.

    Subject VI.1 wants level 1 reproducible from a fixed seed, so 0 must
    not reach the generator.
    """
    assert build_config({"seed": 0}).seed >= MIN_SEED


def test_build_config_negative_seed_is_clamped() -> None:
    """A negative seed is random to the package too."""
    assert build_config({"seed": -1}).seed >= MIN_SEED


def test_build_config_pacgum_density_floor_is_one() -> None:
    """Density 0 would place no pacgums, so the level self-completes.

    "All pacgums eaten" would be true on the first frame and the player
    would win every level instantly.
    """
    assert build_config({"pacgum_density": 0}).pacgum_density >= 1


def test_build_config_accepts_int_for_a_float() -> None:
    """`"level_max_time": 90` must work, not just 90.0."""
    config = build_config({"level_max_time": 90})
    assert config.level_max_time == pytest.approx(90.0)
    assert isinstance(config.level_max_time, float)


def test_build_config_rejects_nan_float() -> None:
    """NaN would freeze a timer forever.

    JSON accepts the bare token NaN, and `nan > 0` is False, so a
    frightened timer set to NaN never counts down and never expires.
    """
    raw = json.loads('{"frightened_time": NaN}')
    config = build_config(raw)
    assert config.frightened_time == GameConfig().frightened_time


def test_build_config_rejects_infinite_float() -> None:
    """Infinity is not a usable duration either."""
    raw = json.loads('{"level_max_time": Infinity}')
    config = build_config(raw)
    assert config.level_max_time == GameConfig().level_max_time


def test_build_config_bool_field_accepts_real_bools() -> None:
    """cheats_enabled reads true/false normally."""
    assert build_config({"cheats_enabled": False}).cheats_enabled is False
    assert build_config({"cheats_enabled": True}).cheats_enabled is True


def test_build_config_bool_field_rejects_truthy_values(
    log_records: RecordingHandler,
) -> None:
    """"yes" and 1 are not bools; guessing the intent is worse."""
    default = GameConfig().cheats_enabled
    assert build_config({"cheats_enabled": "yes"}).cheats_enabled is default
    assert build_config({"cheats_enabled": 1}).cheats_enabled is default
    assert log_records.warnings != []


def test_build_config_filename_rejects_empty() -> None:
    """An empty highscore filename cannot be opened."""
    config = build_config({"highscore_filename": ""})
    assert config.highscore_filename == GameConfig().highscore_filename


def test_build_config_filename_rejects_whitespace() -> None:
    """A whitespace-only name is just as unusable."""
    config = build_config({"highscore_filename": "   "})
    assert config.highscore_filename == GameConfig().highscore_filename


def test_build_config_filename_rejects_a_path() -> None:
    """A separator would write outside the project directory."""
    config = build_config({"highscore_filename": "../../etc/passwd"})
    assert config.highscore_filename == GameConfig().highscore_filename


def test_build_config_filename_rejects_non_string() -> None:
    """A number is not a filename."""
    config = build_config({"highscore_filename": 42})
    assert config.highscore_filename == GameConfig().highscore_filename


def test_build_config_never_raises_on_garbage() -> None:
    """Whatever a reviewer types, the game must still start.

    This is the subject V.3 guarantee in one test: no exception escapes
    build_config, ever.
    """
    garbage: dict[str, object] = {
        "lives": [1, 2, 3],
        "seed": {"nested": "object"},
        "player_speed": "fast",
        "levels": "not a list",
        "fps": None,
        "cheats_enabled": [],
        "highscore_filename": {},
        "points_per_ghost": "many",
        "": "empty key",
    }
    assert isinstance(build_config(garbage), GameConfig)


def test_build_config_result_is_frozen() -> None:
    """Nothing may mutate the settings once they are parsed."""
    config = build_config({})
    with pytest.raises(Exception):
        config.lives = 99  # type: ignore[misc]


# --------------------------------------------------------------------
# levels
# --------------------------------------------------------------------

def test_levels_missing_uses_defaults() -> None:
    """No levels key: use the built-in ladder."""
    assert build_config({}).levels == DEFAULT_LEVELS


def test_levels_not_a_list_uses_defaults() -> None:
    """A string where a list belongs falls back."""
    assert build_config({"levels": "nope"}).levels == DEFAULT_LEVELS


def test_levels_empty_list_uses_defaults() -> None:
    """An empty array means no levels at all, which is unplayable."""
    assert build_config({"levels": []}).levels == DEFAULT_LEVELS


def test_levels_are_read_in_order() -> None:
    """The given sizes come out in the order they were written."""
    raw: dict[str, object] = {
        "levels": [{"width": 12, "height": 9}, {"width": 13, "height": 9}],
    }
    levels = build_config(raw).levels
    assert levels[0] == LevelSpec(12, 9)
    assert levels[1] == LevelSpec(13, 9)


def test_levels_are_padded_to_the_minimum() -> None:
    """Subject VI.7 requires at least ten levels."""
    raw: dict[str, object] = {"levels": [{"width": 12, "height": 9}]}
    assert len(build_config(raw).levels) >= MIN_LEVELS


def test_levels_padding_warns_once(
    log_records: RecordingHandler,
) -> None:
    """One warning for a short list, not one per padded level."""
    build_config({"levels": [{"width": 12, "height": 9}]})
    assert len(log_records.warnings) == 1


def test_levels_full_list_is_not_padded() -> None:
    """Ten given levels stay exactly ten."""
    raw: dict[str, object] = {
        "levels": [{"width": 12, "height": 9}] * MIN_LEVELS,
    }
    assert len(build_config(raw).levels) == MIN_LEVELS


def test_levels_tiny_sizes_are_clamped() -> None:
    """A 1x1 maze makes the package return a wrong-shaped grid."""
    raw: dict[str, object] = {"levels": [{"width": 1, "height": 1}]}
    first = build_config(raw).levels[0]
    assert first.width >= MIN_LEVEL_SIZE
    assert first.height >= MIN_LEVEL_SIZE


def test_levels_huge_sizes_are_clamped() -> None:
    """A 10000-cell maze would never fit a window."""
    raw: dict[str, object] = {"levels": [{"width": 10000, "height": 9}]}
    assert build_config(raw).levels[0].width <= MAX_LEVEL_SIZE


def test_levels_bad_entry_is_skipped(
    log_records: RecordingHandler,
) -> None:
    """A non-object entry is dropped with a warning, the rest survive."""
    raw: dict[str, object] = {
        "levels": [{"width": 12, "height": 9}, "garbage",
                   {"width": 13, "height": 9}],
    }
    levels = build_config(raw).levels
    assert LevelSpec(12, 9) in levels
    assert LevelSpec(13, 9) in levels
    assert log_records.warnings != []


def test_levels_entry_missing_height_uses_a_default() -> None:
    """A half-specified entry is repaired, not dropped."""
    raw: dict[str, object] = {"levels": [{"width": 12}]}
    assert build_config(raw).levels[0].width == 12


def test_levels_bad_size_names_the_level(
    log_records: RecordingHandler,
) -> None:
    """A bad width must say WHICH level entry it was in.

    Every other message in this module names its key.  With ten levels
    and a bad width in the seventh, a bare "width: 1 is out of range"
    leaves the reviewer no way to find the entry to edit.
    """
    good: dict[str, object] = {"width": 14, "height": 10}
    raw: dict[str, object] = {
        "levels": [good] * 6 + [{"width": 1, "height": 9}] + [good] * 3,
    }
    build_config(raw)
    assert any("levels[6].width" in line for line in log_records.warnings)


def test_levels_all_entries_bad_uses_defaults() -> None:
    """Nothing usable in the list at all: fall back."""
    raw: dict[str, object] = {"levels": ["a", 1, None]}
    assert build_config(raw).levels == DEFAULT_LEVELS


def test_default_levels_satisfies_the_minimum() -> None:
    """The built-in ladder must itself be a legal config."""
    assert len(DEFAULT_LEVELS) >= MIN_LEVELS


# --------------------------------------------------------------------
# known_keys and the shipped config.json
# --------------------------------------------------------------------

def test_known_keys_matches_the_dataclass() -> None:
    """Every GameConfig field is a documented key."""
    assert "lives" in known_keys()
    assert "levels" in known_keys()
    assert "unicorn_mode" not in known_keys()


def test_shipped_config_json_has_no_unknown_keys(
    log_records: RecordingHandler,
) -> None:
    """Our own config.json must not log a single INFO or WARNING.

    If this fails, config.json and GameConfig have drifted apart.
    """
    load_config("config.json")
    assert log_records.infos == []
    assert log_records.warnings == []


def test_shipped_config_json_loads_with_expected_values() -> None:
    """The repo config parses to the values the README documents."""
    config = load_config("config.json")
    assert config.lives == 3
    assert config.seed == 42
    assert len(config.levels) >= MIN_LEVELS


def test_load_config_missing_file_raises() -> None:
    """load_config propagates the file errors from read_config_file."""
    with pytest.raises(ConfigError):
        load_config("this_file_does_not_exist.json")
