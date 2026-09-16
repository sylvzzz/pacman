"""Configuration loading with comment support and safe defaults.

Owner: Person A
Planned contents: LevelSpec, GameConfig (frozen dataclass), strip_comments(),
  read_config_file(), build_config() with
  _pick_int/_pick_float/_pick_bool/_pick_filename/_pick_levels clamping
  helpers, load_config().
"""
