# Challenges

The blocking points, bugs and conflicts we hit, and how each was resolved. This
list comes from the git history.

## Movement and collision

The first playable build had the player moving one tile per key press instead
of holding a direction. Fixing it to match the original (press once, keep
moving) then exposed a second bug: some pacgums were not being eaten, because a
variable meant for "the player is not set yet" was also true during normal play.

`Screen.can_move` checked the wrong walls of the neighbour cell, so turns and
collisions worked on some tiles and not others. It was an off-by-one in the
cell-to-tile indexing, made worse by typos in the direction table. We rebuilt
the check against the loader's `(2w+1) x (2h+1)` tile mapping and it held.

## Crash from an unset direction

An AI CI review flagged a case where the player had no direction and the code
tried to read its coordinates, which could crash. We added the guard at the
start of the method rather than at the call site, so every caller is covered.

## Arrow keys moving the player during pause

In the pause menu, up and down were still reaching the game and starting the
player moving. The fix was to have the pause loop send no direction to the
game while a menu owns the input.

## UI performance

The tinted pause window was drawn across the full screen every frame, about
800,000 draw calls per second, and made the game lag on some machines. We
replaced it with a smaller opaque popup panel. This is also what led to the
per-frame caching decisions in `decisions.md`.

## Cheat menu input

Toggling cheats and wiring the menu buttons took several rounds. The exit button
and the row toggling each had their own bugs, and the game kept responding to
cheat keys while the menu was open or a cheat was disarmed. It was settled by
making each row own its key only while it reads `ON`.

## Merge conflicts

Merging `silva` and `dbaltaza` into `testing` produced conflicts, including in
the README, which both of us were editing. The `core`/`ui` boundary kept the
code conflicts small; the text conflicts were the annoying part. We resolved
them by hand and stopped editing the same prose from both sides.

## Config: invalid JSON

A hand-edited config file with invalid JSON surfaced as an ugly failure. It is
now caught and reported as a `ConfigError` with a readable message, per
decision 5.

## Corrupted and duplicate highscores

Two separate problems in the table. First, ghost eyes stayed on screen after a
ghost was eaten (a rendering state bug). Then the table itself: the same name
could appear more than once, and returning runs were summing onto the old
score. It now stores only the single highest run per name.

## What we would change

- Land the `core`/`ui` interface in code (a stub file) sooner, so CI could
  check the boundary, not just us.
- Keep prose in one place per section to avoid README conflicts.
- Profile before the first playable build rather than after it lags.
