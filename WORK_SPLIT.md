# Pac-Man — Work Split (2 people)

Architecture mirrors `M4/pac-man` (same modules, MVC-ish layering), but the package
is split into two sub-packages so ownership is by directory:

- **Person A — `pacman/core/`**: the rules of the game, headless. Nothing in this
  package imports pygame. Everything is unit-tested in `tests/core/`.
- **Person B — `pacman/ui/`** + delivery: window, drawing, screens, input, highscores,
  entry point, packaging, itch.io, project-management docs, README. Tests in `tests/ui/`.

Rule: `pacman.ui` imports `pacman.core`. **`pacman.core` never imports `pacman.ui`
or pygame.** You only ever edit files inside your own directory; if you need
something from the other side, add it to the contract (below) and ask.

---

## Person A — `pacman/core/`

| Module | Subject | Responsibility |
|---|---|---|
| `errors.py` | V.1 | Exception hierarchy: `PacManError` → `UsageError`, `ConfigError`, `MazeGenerationError`, `HighscoreError`. Every failure the user can see is one of these. |
| `log.py` | V.3 | `get_logger()` writing clear WARNING/INFO lines to stderr. |
| `config.py` | V.2, V.3 | `strip_comments()` (`#` and `//` lines), `read_config_file()`, `build_config()` with `_pick_int/_pick_float/_pick_bool/_pick_filename/_pick_levels` clamping helpers, frozen `GameConfig` + `LevelSpec`. Unknown keys → INFO, bad values → WARNING + default/clamp, ≥10 levels guaranteed. Owns `config.json`. |
| `maze_loader.py` | V.4 | The **only** module importing `mazegenerator`. `MazeGenerator(size, perfect=False, entry_cell, exit_cell, seed)`, read `gen.maze` (bitmask N=1 E=2 S=4 W=8), validate shape, treat fully-closed cells (the "42" glyph) as solid, expand to a `(2w+1)×(2h+1)` bool tile grid. Every failure → `MazeGenerationError`. |
| `level.py` | VI.1, VI.4 | `Level` + `create_level()`: player spawn = corridor tile nearest the centre, seal tiles unreachable from it, 4 reachable tiles nearest the corners = ghost spawns + super-pacgums, pacgums on `pacgum_density`% of remaining corridors, cached BFS distance maps per target tile. Level 1 uses `seed`, others random (≥1, since the package treats 0 as random). |
| `entities.py` | VI.2, VI.3 | `Direction`, `Mover` (tile-to-tile interpolation at `speed` tiles/s, turns only at tile centres), `Player` (buffered turn, lives), `GhostState`, `Personality`, `Ghost` (home corner, frightened/eaten timers). |
| `ghost_ai.py` | VI.3 | `chase_target()` per personality (Blinky = player, Pinky = 4 ahead, Inky = player + 30 % random, Clyde = player when far / corner when close), flee = maximise BFS distance with 15 % random, no U-turn unless dead end, `choose_ghost_direction()`. |
| `game.py` | VI.2, VI.5, VI.6, VI.7 | `Phase`, `Cheats`, `Game`: `update(dt)` with `dt` capped at 100 ms, collisions at Manhattan distance < 0.6 tile, score (never decreases), lives, level timer (timeout → lose a life, restart timer), frightened timer, level progression carrying score + lives, pause, READY freeze, cheat switches (invincible, freeze, speed, +life, skip, frighten, +time). |
| `tests/core/test_config.py`, `test_maze_loader.py`, `test_level.py`, `test_entities.py`, `test_game.py`, `tests/conftest.py` | III.3 | Headless pytest suite; `small_config` fixture with tiny levels for fast simulations. Include faulty-config and broken-package cases. |
| README sections | IX | **Configuration**, **Maze Generation**, **Implementation**, model half of **General Software Architecture**. |

**Mid-point deliverable:** `Game` drivable from a REPL:
`g = Game(config); g.start(); g.set_direction(Direction.LEFT); g.update(0.016)`,
with `g.player`, `g.ghosts`, `g.level`, `g.score`, `g.lives`, `g.time_left`,
`g.phase` readable.

---

## Person B — `pacman/ui/` & delivery

| Module | Subject | Responsibility |
|---|---|---|
| `highscores.py` | V.5 | `HighscoreEntry`, `sanitize_name()` (≤10 chars, alphanumeric + spaces), `is_valid_score()`, `HighscoreTable`: load tolerant of missing/corrupt file, keep top 10 sorted, atomic save (temp file + rename), `HighscoreError` on unwritable path. `tests/ui/test_highscores.py`. *(Model-style module, but independent of the game rules; lives in `ui/` so B owns it.)* |
| `blockfont.py` | IV | 5×7 block glyphs for **all** text (`pygame.font` has no MLX equivalent). `width()`, `height()`. |
| `renderer.py` | IV, VI.8 | `Canvas` (pixel-buffer writes, hand-rasterised rects/circles/scanlines) and `Renderer` (owns the window; draws menu, pages, maze image cached once per level, entities, HUD with score/lives/level/time, pause and end panels). **Only MLX-equivalent pygame calls** — see the table in `CLAUDE.md` and `notes.txt`. |
| `scenes.py` | VI.8 | `Scene` base, `MenuScene` (Start / Highscores / Instructions / Exit), `HighscoresScene`, `InstructionsScene`, `PlayScene` (pause overlay, cheat keys C + F1..F7), `EndScene` (game over / victory, name entry, ESC skips), `new_game()` mapping failures to `PacManError`. |
| `app.py` | IV | `App`: one `Renderer`, one `HighscoreTable`, current `Scene`; delta-time loop on `time.perf_counter`, key dispatch, `_char_for_key()`. |
| `pac-man.py` | V.1 | `parse_arguments()` (exactly one `.json` arg → `UsageError`), `main()` mapping `PacManError` to exit codes 2 / 1 / 130. Never a traceback. |
| `notes.txt` | IV | Keep the pygame → MLX equivalence list current; it becomes the **Graphics** README section. |
| `pac-man.spec`, `packaging/` | VII | PyInstaller spec at root, `make package` → `dist/pac-man/`, `INSTRUCTIONS.txt` shipped in the build, itch.io unlisted upload, URL recorded in `packaging/README.md`. |
| `project_management/` | VIII | Owns the structure (timeline, kanban, analysis, risks, test plan, retrospective). Both fill in their rows. |
| `README.md` | IX | Owns the skeleton, first italic line with both logins, **Description**, **Instructions**, **Highscore**, **Graphics**, **Project Management**, **Resources / AI usage**, view half of **General Software Architecture**. |

**Mid-point deliverable:** the full screen flow (menu → play → end → name → menu)
running against a **stub** `Game` so screens can be built before the model is done.

---

## Contract between the two halves

Fix these names on day 1; everything else may change independently.

- `core.config.GameConfig` fields = the keys in `config.json` (A owns, both read).
- `core.entities.Direction` with `.dx/.dy`; `Mover.x`, `Mover.y` (floats, tile units),
  `Mover.direction`; `Player.lives`; `Ghost.state`, `Ghost.personality`, `Ghost.home`.
- `core.level.Level`: `width`, `height` (tiles), `is_wall(x, y)`, `pacgums`, `super_pacgums`
  (sets of `(x, y)`), `player_spawn`, `ghost_spawns`.
- `core.game.Game`: `start()`, `update(dt)`, `set_direction(d)`, `toggle_pause()`,
  `cheats: Cheats`, `phase: Phase` (READY / PLAYING / PAUSED / LEVEL_WON / GAME_OVER /
  VICTORY), `score`, `lives`, `level_index`, `level_count`, `time_left`,
  `player`, `ghosts`, `level`.
- `core.errors.PacManError` hierarchy is shared: core raises, `pac-man.py` and
  `ui.scenes.new_game()` catch.

`Renderer` only *reads* `Game`. `scenes` are the only place that *calls* `Game`.

---

## Shared responsibilities

- `make lint-strict` and `make test` clean on every push.
- Cross-review every PR; no merge to `main` without the other's approval.
- Day-1 decisions together: confirm the `mazegenerator` 2.1.0 interface from
  `vendor/`, lock the contract above and the `config.json` keys, set up the Kanban.

---

## Suggested timeline

| Week | Person A — Model | Person B — View / Delivery |
|---|---|---|
| 1 | `errors`, `log`, `config` + tests; `maze_loader` against the vendored wheel | `blockfont`, `Canvas`, `App` loop, `MenuScene`, `pac-man.py`, PM docs structure |
| 2 | `level` (BFS, spawns, pellets), `entities` movement | `Renderer` maze/entities/HUD against a stub `Game`, `PlayScene` + pause |
| 3 | `game` (collisions, timers, progression, cheats), `ghost_ai` | `highscores` + tests, `HighscoresScene`, `InstructionsScene`, `EndScene` name entry |
| 4 | Ghost personality tuning, edge cases, faulty-config torture tests | Wire real `Game`, `pac-man.spec`, `make package`, itch.io, README |
| 5 | Integration bugs, defense prep (recode drills on model) | Integration bugs, acceptance test log, defense prep (recode drills on UI) |

---

## Directory layout

```
pacman-git/
├── pac-man.py              B  entry point (imports pacman.ui.app)
├── pac-man.spec            B  PyInstaller spec
├── config.json             A  default config with # comments
├── notes.txt               B  pygame calls without MLX equivalent → replacements
├── Makefile  .flake8  mypy.ini  requirements.txt
├── README.md               B skeleton, sections per owner
├── WORK_SPLIT.md           this file
├── pacman/
│   ├── core/               A  — headless, no pygame
│   │   ├── errors.py  log.py  config.py  maze_loader.py
│   │   └── level.py  entities.py  ghost_ai.py  game.py
│   └── ui/                 B  — imports core
│       ├── highscores.py  blockfont.py  renderer.py
│       └── scenes.py  app.py
├── tests/
│   ├── conftest.py         shared fixtures
│   ├── core/               A  one test_*.py per core module
│   └── ui/                 B  test_highscores.py (+ any headless ui tests)
├── project_management/     B owns structure, both fill in
├── packaging/              B  INSTRUCTIONS.txt + itch.io notes
└── vendor/                 mazegenerator-2.1.0 wheel, unmodified
```
