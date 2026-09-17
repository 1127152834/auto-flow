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
