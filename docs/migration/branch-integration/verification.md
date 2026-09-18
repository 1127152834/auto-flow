# Valid branch integration verification

Date: 2026-09-17 17:08 CST

Status: passed

Environment: macOS Darwin 25.4.0 arm64, Node.js 26.7.0, uv 0.10.6, backend Python 3.11.13.

Verified commit before this report: `598b08dc3d98c123d5884bb91de90cc5ce01e2a9`.

## Release checks

| Check | Result | Evidence |
| --- | --- | --- |
| Full backend suite | passed | `2935 passed, 13 skipped`, 426.71 seconds |
| Full desktop suite | passed | `380` files and `5293` tests, 190.08 seconds |
| Focused migration suite | passed | `33 passed` |
| Alembic graph | passed | one head: `0013_merge_project_runtime` |
| TypeScript typecheck | passed | exit 0 |
| ESLint | passed | exit 0 |
| Electron/Vite production build | passed | main, preload, and renderer bundles built |
| Repository structure tests | passed | `3 passed` |
| Script tests | passed | `66 passed`; a second run confirmed generated-inventory determinism |
| Generated OpenAPI check | passed | exit 0, no generated client drift |
| Table-system verifier | passed | all `25` registered table surfaces covered |
| Sidecar smoke | passed | sidecar launched and exited cleanly |
| Desktop smoke | passed | desktop connected in development mode on Darwin/arm64; sidecar exited after desktop termination |
| Android scripts | passed within integration boundary | both management and handoff scripts parsed `--help`; no emulator or user device was started |

The Alembic discovery command was run with the repository's explicit configuration path:

```bash
uv run --directory apps/backend alembic \
  -c src/autoflow/infrastructure/database/alembic.ini heads
```

The shorter command without `-c` cannot discover this repository's nested `alembic.ini`; it failed before loading the migration graph and was replaced by the explicit command above.

## Git and worktree invariants

All of these branches are ancestors of the integrated commit:

- `codex/project-management-pm3@2bac1b14`
- `codex/project-management-pm4@fbda6f17`
- `codex/project-management-pm5@fbda6f17`
- `codex/android-workflow-handoff@f573a44d`
- `codex/global-table-system@2a29ac0d`
- `codex/ui-controls-plan@1fb58e18`
- `codex/proxy-management@0ad2fd2a`

The intended historical exclusions remain non-ancestors:

- `codex/m6-unfinished-checkpoint-20260913@59ae8d44`
- `codex/studio-before-removal-20260913@4eda2074`

The integration worktree was clean after the checks. The protected original checkout remained on `codex/pre-branch-integration-wip-20260917`, and its final fingerprints exactly matched the pre-integration values:

| Fingerprint | SHA-256 |
| --- | --- |
| status/path set | `5a01adf85b7c78fc771a69f2f4be9e435ada5414b640688e969929c3fd201416` |
| tracked content delta | `81243a19cc0e628ed4f05cbbe91848faa6610628c052b621487d723bf44e6459` |
| untracked content set | `786c4c4426ccfb98ecde8a58f771f0f69f434e4de771219b246e1dd9ee7634ec` |

## Explicitly unrun checks and remaining boundary

- No real Android emulator/device was started and no Android user data was modified.
- No live ProxyPanel credentials or remote write operations were used.
- Windows, other CPU architectures, packaged-install testing, and user manual acceptance were not run on this macOS host.
- Android device management and manual control are integrated. Workflow allocation/takeover still returns the documented typed unavailable errors because the source implementation depended on the retired workflow runtime; it requires a separate adapter to the current Studio executor before it can be enabled.

## Post-integration sidecar recovery

The first launch against the user's existing workspace exposed an omitted historical migration revision: the database was at `0013_workflow_custom_modules`, created by protected uncommitted Studio work, while the integrated graph initially ended its Studio parent at `0012_workflow_document_requests`. Alembic correctly refused to guess and the sidecar exited before readiness.

The exact historical migration was restored and `0013_merge_project_runtime` now merges `0013_workflow_custom_modules` with `pm06_project_capability_reads`. A regression test creates that historical database, inserts custom-module and idempotency-request rows, upgrades twice, and verifies the rows plus foreign keys. The focused migration suite passed `34` tests; the complete backend suite then passed `2936` tests with `13` conditional skips. A SQLite-consistent copy of the user's real database upgraded to the single integrated head and a sidecar launched from it emitted `AUTOFLOW_READY`.

## Re-verification of the publish head (2026-09-18)

Date: 2026-09-18 11:20 CST

Status: passed

Environment: macOS Darwin 25.4.0 arm64, Node.js 26.7.0, uv 0.10.6, backend Python 3.11.13.

Verified commit: `c5214ecb2a7f1bb73aa1039f75cfa8e2f0371a59` (`codex/integrate-valid-branches-20260917`).

This rerun covers the two commits added after the 2026-09-17 report: `1bfa57f7` (custom-module migration history) and `c5214ecb` (project overview header unification).

| Check | Result | Evidence |
| --- | --- | --- |
| Full backend suite | passed except one flaky test | `2935 passed, 13 skipped, 1 failed`; the failure is the timing-bound crash test below |
| Flaky crash test rerun in isolation | passed 5 of 5 | `test_browser_child_crash_releases_worker_slot_for_next_run`, each run under 1.5 s |
| Full desktop suite | passed | `380` files and `5294` tests |
| Projects domain tests | passed | `12` files, `92` tests |
| TypeScript typecheck | passed | exit 0 |
| ESLint | passed | exit 0 |
| Electron/Vite production build | passed | main, preload, and renderer bundles built |
| Repository structure tests | passed | `3 passed` |
| Generated OpenAPI check | passed | exit 0, no generated client drift |
| Alembic graph | passed | one head: `0013_merge_project_runtime` |
| Fast-forward eligibility | passed | `codex/architecture-baseline` is an ancestor of this commit |

The full backend run produced exactly one failure, in `tests/integration/test_b1_stop_and_browser_crash_regressions.py::test_browser_child_crash_releases_worker_slot_for_next_run`. The test waits at most `1.0 s` for a child-process exit callback to clear `manager.busy()`; under the load of the parallel suite the callback landed after that window. The same test passes 5 of 5 in isolation and the surrounding file passes on its own, so this is a load-sensitive timing flake in the test harness, not a regression in the crash-recovery path. Hardening the wait budget is a separate test change and was not made here.

The 2026-09-17 boundary notes still apply unchanged: no real Android runtime, no live ProxyPanel credentials, and no Windows or packaged-install testing were performed.

## PM5 integration (2026-09-18)

Date: 2026-09-18 15:05 CST

Status: passed

Merged: `codex/project-management-pm5` (`34c43f7c`, `ed6b0fd4`, `5b8327e2`) into `codex/integrate-valid-branches-20260917` as `851097fd`, then `6d9d0f19` (pre-existing ruff import order on the target branch) and `dd52e56b` (PM5 QA rerun on the integrated head).

Conflict resolution kept the target branch's dual runtime composition and re-applied PM5's environment wiring on top of it:

- `bootstrap/app.py` / `bootstrap/workflows.py`: `EnvironmentStore`, `EnvironmentBrowserLauncher` and `EnvironmentService` are injected into `configure_project_workflow_runtime`, `ProjectAutomationResourceQuery`, `ProjectRunResourceResolver`, `ProjectRunCoordinator`, `ProjectBatchScheduler` and `ProjectHttpServices`; the execution-generation lookup reads `app.state.project_workflow_runtime`.
- `providers/browser/workflow_worker.py` stays on the target branch (that path is now the Studio worker); PM5's persistent-context branch moved to `providers/browser/project_workflow_worker.py`, which is the worker project runs actually use.
- `ProjectOverviewPage.tsx` stays on the target branch's R1 layout (density comes from `ProjectHeader`); PM5's per-tab width special case was dropped.
- `generated.ts` and `docs/migration/studio-frontend-completion/*` were regenerated from the merged sources.
- The migration graph keeps one head: `pm07_environments` now declares `down_revision = "0013_merge_project_runtime"`, and the head assertions in the migration tests were updated.

| Check | Result | Evidence |
| --- | --- | --- |
| Full backend suite | passed | `2987 passed, 16 skipped` |
| Migration and compatibility subset | passed | `71 passed` |
| Ruff | passed | `All checks passed!` after `6d9d0f19`; the 26 flagged files were already flagged at `2685361f` |
| mypy | passed | 363 source files |
| Full desktop suite | passed | `389` files and `5325` tests |
| TypeScript typecheck / ESLint | passed | exit 0 |
| Electron/Vite production build | passed | main, preload, and renderer bundles built |
| Generated OpenAPI check | passed | no generated client drift |
| Repository structure and script checks | passed | `test:structure` 3/3, `test:scripts` 66/66 |
| Real Electron + FastAPI + SQLite + CloakBrowser QA | passed | `docs/project-management/implementation/pm5/qa-runs/2026-09-18/ui-result.json`, 16 checkpoints / 27 screenshots at `6d9d0f19` |
| Fast-forward eligibility | passed | `codex/architecture-baseline` is an ancestor of this commit |

Unchanged boundaries: the real production execution core is still not wired (the report reads "management side and real browser storage verified / real execution core pending"); Windows, other architectures, packaged installs and user manual acceptance were not run.
