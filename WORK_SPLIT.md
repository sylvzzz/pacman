# Pac-Man — Work Split (2 people)

The project is split along the one seam that keeps the two halves independent:
**game logic (headless)** vs **presentation & delivery (graphics, menus, packaging)**.

- **Person A — Core**: everything that makes the game *work* without a window.
  Lives in `src/core/`. Fully unit-testable with pytest, no graphics import.
- **Person B — UI & Delivery**: everything the player *sees and touches*, plus
  shipping the build. Lives in `src/ui/`, `pac-man.py`, packaging, docs.

The rule: `src/ui/` imports from `src/core/`. `src/core/` **never** imports from
`src/ui/`. If you need something from the other side, ask for it on the interface
(see "Contract" below) rather than reaching across.

---

## Person A — Core (`src/core/`)

| Module | Subject section | Responsibility |
|---|---|---|
| `core/config.py` | V.1, V.2, V.3 | Load the JSON config, strip `#` (and `//`, `/* */`) comments, validate every key, clamp bad values to defaults, ignore unknown keys, log clear messages. Expose a frozen `GameConfig` dataclass. |
| `core/maze.py` | V.4, VI.1 | Adapter around the assigned **A-Maze-ing** package. Call it with `PERFECT=False`, convert its output to our own `Grid` (walls / corridors). Catch every generator failure and raise a single `MazeGenerationError`. |
| `core/level.py` | VI.1, VI.4 | Build a `Level` from a `Grid`: place pacgums in corridors, super-pacgums in the 4 corners, 4 ghost spawns in the corners, player spawn in the middle. Fixed seed for level 1, random for the rest. |
| `core/entities/player.py` | VI.2 | Position, direction, queued direction, movement through corridors only, lives, respawn. |
| `core/entities/ghost.py` | VI.3 | Autonomous movement, chase behaviour (distance-based), flee when edible, eaten → respawn to corner after N seconds, freeze flag for cheat mode. |
| `core/game.py` | VI.2, VI.6, VI.7 | The `Game` state machine: tick(dt), collisions, scoring (X/Y/Z, never decreases), edible timer, level timer, level progression (score + lives carried), win / lose detection, pause. |
| `core/cheats.py` | VI.5 | `CheatState` toggles: invincibility, level skip, ghost freeze, extra life, speed boost. Pure flags that `game.py` consults. |
| `core/highscore.py` | V.5 | Load/save JSON, tolerate missing/corrupt file, validate name (≤10 chars, alphanumeric + spaces), non-negative int scores, keep top 10 sorted. |
| `tests/core/` | III.3 | pytest for all of the above, including faulty configs and broken highscore files. |
| `Makefile` | III.2 | `install`, `run`, `debug`, `clean`, `lint`, `lint-strict`. |

**Deliverable for the mid-point:** a `Game` you can drive from a Python REPL
(`g.tick(0.016)`, `g.set_direction(Direction.LEFT)`) and observe via `g.snapshot()`.

---

## Person B — UI & Delivery (`src/ui/`, root)

| Module | Subject section | Responsibility |
|---|---|---|
| `ui/graphics.py` | IV | Thin wrapper over the chosen MLX-compatible library. **Only** functions with an MLX equivalent: create window, put pixel / image, key & loop hooks, destroy. Nothing else in `ui/` touches the library directly. |
| `ui/assets.py` | VI.8 | Sprite / colour definitions for walls, pacgums, super-pacgums, Pac-Man, ghosts (normal, edible, eaten). |
| `ui/input.py` | VI.2, VI.5 | Key mapping: arrows + WASD → `Direction`, `P`/`Esc` → pause, cheat keys → `CheatState`. |
| `ui/screens/menu.py` | VI.8 | Main menu: Start, Highscores, Instructions, Exit. |
| `ui/screens/highscores.py` | V.5, VI.8 | Top-10 table, read from `core.highscore`. |
| `ui/screens/instructions.py` | VI.8 | Controls + rules + cheat keys. |
| `ui/screens/game.py` | VI.8 | Renders the `Game` snapshot every frame + HUD (score, lives, level, time left). |
| `ui/screens/pause.py` | VI.8 | Resume / Return to main menu. |
| `ui/screens/end.py` | VI.8 | Game-over and Victory screens: final score, message, name entry box, save → menu. |
| `ui/app.py` | IV (Game Loop) | Screen manager / top-level loop: Menu → Game → End → Name → Menu. Owns the timing loop and hands `dt` to `core.Game`. |
| `pac-man.py` | V.1 | Entry point: exactly one argv (the config), friendly error for anything wrong, never a traceback. |
| `packaging/` | VII | PyInstaller spec (or equivalent) at the root, `itch.io` unlisted build, in-package `INSTRUCTIONS.txt`. |
| `docs/project_management/` | VIII | Kanban / timeline, progress tracking, risk analysis, team organisation, acceptance test plan. (Both fill it in, B owns the structure.) |
| `README.md` | IX | Skeleton with every required section. Each person writes the sections for their own modules. |

**Deliverable for the mid-point:** the full screen flow working with a
**fake** `Game` (a hard-coded snapshot) so UI can be built before Core is done.

---

## Contract between the two halves

Agree on this **on day 1** and put it in `src/core/types.py`. Everything else can
change independently.

```python
class Direction(Enum): UP, DOWN, LEFT, RIGHT

class Cell(Enum): WALL, CORRIDOR, PACGUM, SUPER_PACGUM

@dataclass(frozen=True)
class GhostView:      # what the UI needs to draw one ghost
    x: int; y: int; edible: bool; eaten: bool

@dataclass(frozen=True)
class Snapshot:       # read-only view of the game, produced every frame
    grid: tuple[tuple[Cell, ...], ...]
    player_x: int; player_y: int; player_dir: Direction
    ghosts: tuple[GhostView, ...]
    score: int; lives: int; level: int; levels_total: int
    time_left: float
    paused: bool
    status: GameStatus   # RUNNING | LEVEL_WON | GAME_WON | GAME_OVER

class Game:           # the only object UI holds
    def __init__(self, config: GameConfig) -> None: ...
    def tick(self, dt: float) -> None: ...
    def set_direction(self, d: Direction) -> None: ...
    def toggle_pause(self) -> None: ...
    def cheats(self) -> CheatState: ...
    def snapshot(self) -> Snapshot: ...
```

UI never mutates game state except through `set_direction`, `toggle_pause`
and `cheats()`. Core never knows what a pixel is.

---

## Shared responsibilities

- **Both**: flake8 + mypy clean on every push (`make lint`). Docstrings + type hints.
- **Both**: write your own README sections and your own rows in the acceptance
  test plan.
- **Both**: review each other's PRs. No merge to `main` without the other's
  approval — this is also the "peer review" the AI-instructions chapter demands.
- **Day 1 decisions (together)**: graphics library, A-Maze-ing package interface
  check, `types.py` contract, config key names, Kanban tool.

---

## Suggested timeline

| Week | Person A — Core | Person B — UI & Delivery |
|---|---|---|
| 1 | `types.py`, `config.py` (+ tests), `maze.py` adapter | `graphics.py` wrapper, `app.py` loop, main menu, `pac-man.py`, Makefile skeleton, PM docs structure |
| 2 | `level.py`, `player.py`, `ghost.py`, `game.py` tick + collisions | Game screen rendering against a fake snapshot, HUD, input, pause |
| 3 | Scoring, timers, level progression, cheats, `highscore.py` | End / victory / name-entry screens, highscores & instructions screens, wire real `Game` |
| 4 | Ghost AI polish, edge cases, faulty-config torture tests | Packaging, itch.io upload, README, PM docs, acceptance tests |
| 5 | Integration bugs, defense prep (recode drills on core) | Integration bugs, defense prep (recode drills on UI) |

---

## Directory layout

```
pacman-git/
├── pac-man.py                 # B — entry point
├── config.json                # A — default config (with # comments)
├── Makefile                   # A
├── README.md                  # both
├── WORK_SPLIT.md              # this file
├── subject.md
├── packaging/                 # B — build spec + in-package instructions
├── docs/project_management/   # B owns structure, both fill in
├── src/
│   ├── core/                  # A — headless game logic
│   │   ├── types.py           # shared contract
│   │   ├── config.py
│   │   ├── maze.py
│   │   ├── level.py
│   │   ├── game.py
│   │   ├── cheats.py
│   │   ├── highscore.py
│   │   └── entities/
│   │       ├── player.py
│   │       └── ghost.py
│   └── ui/                    # B — everything graphical
│       ├── graphics.py
│       ├── assets.py
│       ├── input.py
│       ├── app.py
│       └── screens/
│           ├── menu.py
│           ├── highscores.py
│           ├── instructions.py
│           ├── game.py
│           ├── pause.py
│           └── end.py
└── tests/
    ├── core/                  # A
    └── ui/                    # B
```
