# Decisions

The technical and process choices that shaped the project, with the reasoning
behind each one.

## 1. Hard split between game rules and graphics

**Decision.** `pacman.core` never imports pygame or `pacman.ui`. `pacman.ui`
imports `core`.

**Why.** The subject asks for the game rules to stay independent from the
graphics code. The split also gave us two clean workstreams (see
`organization.md`) and, more usefully, let the rules be tested with no window
open. That is the reason the whole `make test` suite can run headless on CI.

## 2. One module owns the maze package

**Decision.** Only `pacman/core/maze_loader.py` imports `mazegenerator`.

**Why.** The package is used as-is and could be swapped. Keeping the import in
one place means a change to the package format touches one file, not the game.

## 3. `perfect=False`

**Decision.** Every level is generated with `perfect=False`.

**Why.** A perfect maze has no loops, so dead ends exist and a chased player
can be cornered with no escape. With `perfect=False` the corridors form loops
and the player always has an out, which matches arcade Pac-Man.

## 4. Draw everything by hand, no `pygame.draw` or `pygame.font`

**Decision.** No `pygame.draw`, `pygame.font`, `transform` or `mixer`. Text and
sprites are hand-rasterised (`blockfont.py`, `figures.py`, `maze.py`).

**Why.** The project targets an MLX equivalent of every pygame call. MLX has no
font loader, no anti-aliasing, no shape drawing, no scaling or rotation, and no
sound. Drawing by hand from `mlx_pixel_put`-level primitives is the only path
that stays inside that constraint. Full list of substitutions is in
`notes.txt`.

## 5. Bad config values clamp, they do not crash

**Decision.** The parser only exits on an unreadable file or invalid JSON.
Missing keys take their default silently, out-of-range values are clamped with
a `WARNING`, unknown keys are ignored with an `INFO`.

**Why.** A typo in a config file should not cost the reviewer a run. The game
starts with something sensible and tells you what it changed on stderr.

## 6. Cache everything that repeats per frame

**Decision.** The maze is drawn once per level onto a surface and only blitted
after. The maze origin, pellet "stamps" and menu decoration are cached.

**Why.** The first playable build lagged. Profiling pointed at work being redone
every frame, in particular the tinted pause window, which was issuing around
800,000 draw calls per second. Moving the repeated work into caches (mostly in
`renderer.py`) removed the lag more cleanly than rewriting the draw path.

## 7. Highscores: one row per name, validated on load, atomic saves

**Decision.**

- One row per name; a returning player replaces their row only on a higher score.
- Names are at most 10 characters (letters, digits, spaces), scores are
  non-negative integers.
- Save goes to a temp file and is renamed over the target.

**Why.**

- One row per name stops a single player from filling the whole table.
- Validating on load means a hand-edited or corrupted file is rejected, not
  trusted, so it cannot break the game.
- Renaming is atomic on the filesystem, so a crash or Ctrl+C mid-write never
  leaves a half-written table behind.

## 8. Errors are typed and mapped at the top

**Decision.** Every user-triggerable error is a `PacManError` subclass, caught
in `pac-man.py` and printed as one readable line. Exit codes: 2 usage, 1 error,
130 interrupt.

**Why.** No traceback should reach a player. A single catch at the entry point
is simpler than guarding every call site.

#### Overall, our best aproach was to not change eachother´s work, we build a pipeline to adapt each work to ours.