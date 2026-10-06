# Project management

Two-person project. Task ownership is in [`../WORK_SPLIT.md`](../WORK_SPLIT.md).

| File | Content |
| --- | --- |
| [timeline.md](timeline.md) | Planned schedule versus actual progress |
| [kanban.md](kanban.md) | Task board (done / in progress / to do), one column per person |
| [analysis_and_decisions.md](analysis_and_decisions.md) | Requirement analysis and the technical choices made |
| [risks.md](risks.md) | Risk register with mitigations and outcome |
| [test_plan.md](test_plan.md) | Acceptance test plan and execution log |
| [retrospective.md](retrospective.md) | Blocking points, conflicts, what worked, what did not |

Method: requirements are extracted from the subject into a checklist
(`test_plan.md`), split into tasks on the Kanban board, and scheduled on
the timeline. A task is done when its acceptance tests pass, `make
lint-strict` is clean, and the other person has reviewed the PR.
