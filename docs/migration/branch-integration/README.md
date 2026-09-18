# Valid branch integration

Date: 2026-09-17

Target: `codex/architecture-baseline`

Integration branch: `codex/integrate-valid-branches-20260917`

This integration preserves the current Studio as the authoritative runtime while consolidating valid project execution, Android device management, shared UI/table, and proxy-management work. Capability ports are ordinary commits; reconciliation merges only record reviewed historical branches after confirming that the merge leaves the tree unchanged.

## Capability evidence

- Project management PM3/PM4: real merge `a5c5ed98`; project workflow tables are isolated under `project_workflow_*` and joined by migration `0013_merge_project_runtime.py`.
- Project management PM5: real merge `851097fd` (persistent login environments and manual intervention), followed by the import-order fix `6d9d0f19` and the QA rerun `dd52e56b`. `pm07_environments` now hangs off `0013_merge_project_runtime`, so the graph keeps a single head: `pm07_environments`.
- [Android capability matrix](android-capability-matrix.md): device lifecycle, persistence, environments, batch creation, console, and manual control are integrated. Workflow allocation/takeover remains explicitly unavailable until adapted to the current runtime.
- [UI and table matrix](ui-table-capability-matrix.md): missing isolated controls were ported; current Studio/project tables and option-based component APIs were retained.
- [Proxy matrix](proxy-capability-matrix.md): the current implementation covers the original management branch and the later remote-control line.
- [Final verification](verification.md): fresh full-suite, migration, build, smoke, graph, and protected-worktree evidence.

## Branch graph assertions

These commands must exit zero on the integrated target:

```bash
for b in codex/project-management-pm3 codex/project-management-pm4 codex/project-management-pm5 codex/android-workflow-handoff codex/global-table-system codex/ui-controls-plan codex/proxy-management; do
  git merge-base --is-ancestor "$b" HEAD
done

for b in codex/m6-unfinished-checkpoint-20260913 codex/studio-before-removal-20260913; do
  ! git merge-base --is-ancestor "$b" HEAD
done
```

The excluded branches are historical checkpoints, not missing product work: M6 was unfinished, and `studio-before-removal` captures a superseded pre-removal state.

## Worktree safety

The user's original dirty checkout is protected on `codex/pre-branch-integration-wip-20260917`. Integration is performed in a clean linked worktree. Before updating and pushing the target branch, the original checkout's status, tracked-content, and untracked-content fingerprints are recomputed and compared with their pre-integration values.
