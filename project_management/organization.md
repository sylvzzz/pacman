# Team organization

Two people, `dbotelho` and `dbaltaza`. The project ran from 7 September to
8 October 2026.

## Ownership

We split the work along the architecture boundary described in the main
README: `pacman.core` never imports pygame, `pacman.ui` imports `core`.

| Person | Owns | Modules |
| --- | --- | --- |
| dbaltaza | game backend | `pacman/core/*` (config, maze_loader, level, entities, ghost_ai, game) |
| dbotelho | front end | `pacman/ui/*` (renderer, scenes, app, blockfont, figures, maze, highscores) |

The boundary doubles as the contract between us. Because `core` cannot import
`ui`, each of us could work and test without touching the other's files. The
interface was agreed before any code was written.

## Branches and review

- Each person worked on their own branch: `silva` (dbotelho) and `dbaltaza`
  (dbaltaza).
- `testing` was the integration branch. Both features were merged there first,
  then into `main` once they held together.
- Merges went through pull requests. Pull request #1 was the first core drop;
  after that we kept using PRs for review.

## CI/CD

Every push and pull request runs `.github/workflows/ci.yml`:

1. `flake8 .`
2. `mypy .` with the project flags (`--disallow-untyped-defs`,
   `--check-untyped-defs`, ...)

A second workflow, `.github/workflows/ai-review.yml`, runs a free model from
build.nvidia.com on the diff of every PR and every push.

It posts a review comment covering both packages. We treated it as
a second reviewer, not an authority, it flagged edge cases we had missed and
suggested changes we accepted or rejected by hand. One example we kept is the
`Screen.can_move` neighbour-wall check, one example we rejected is a full
rewrite of `Screen.render_maze`, which we reviewed and declined for now.

## How we made decisions

- Anything that crosses the `core`/`ui` boundary is a two-person decision.
- Anything inside one package is that owner's call, as long as it keeps the
  boundary and passes CI.
- Disagreements were settled by reading the subject requirement and, when it
  did not say, by picking the option that kept the game rules testable without
  a display.

## Tooling

- `make install` / `run` / `lint` / `package`.
- pytest for the automated suite, which led us into the habit of pushing logic
  into `core` so it could be tested headless.
