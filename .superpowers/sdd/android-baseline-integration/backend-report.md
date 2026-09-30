# Backend merge integration

- Date: 2026-09-24. Status: confirmed scoped verification; full combined suite and packaging owned by parent task.
- Checkout: `/Users/zhangtiancheng/.codex/worktrees/android-baseline-integration/autoflow`.
- Merge: baseline `c6e02427` + Android `746c9c5b`; actual merge base `31bfbb514bb2dc56cf9a4213448c06bc0ef74400` (initial brief's `a92f0688` was not the merge base).
- Ownership: backend files only; 24 explicitly scoped files staged. No commit, no source worktree changes, no frontend/generated API edits.
- Import verification: `PYTHONPATH=src .venv/bin/python -c 'import autoflow; print(autoflow.__file__)'` resolves this checkout's `apps/backend/src/autoflow/__init__.py`, despite the shared venv symlink.

## Decisions

1. Combine PyInstaller runtime assets/binaries: keep PM9 required-fields JSON and macOS cryptography OpenSSL ABI binaries alongside Android-branch Studio ML dynamic libraries. Spec compiles; no packaging success claimed.
2. Keep metadata router and all added workflow/Android services. Preserve static route ordering. Keep optional worker command bus for PM9 canvas-subflow callers while binding all Studio interactive gateways when present; retain both node boundary and debugger.
3. Preserve PM9 loop completion bookkeeping and stop suppression alongside Android loop-local restoration and tracked-variable events. Keep PM9 cancellation's `finally` sensitive-taint propagation; reject the auto-merged tuple-unpacking mismatch.
4. Preserve PM9 platform/PID identity safety in Android runtime, including no `kill(pid, 0)` fallback for unknown birth. Keep Android management/backup/command-receipt additions and all new runtime tests.
5. Add only `0020_merge_android_pm9` with parents `am01_management_operations` and `pm10_shared_sheet_cursors`. Existing migrations are unchanged. New parametrized regression creates real SQLite databases at each prior head, seeds a workflow and Android receipt where applicable, performs the production migration twice, checks data preservation, both feature schemas, PM9 cursor unique constraint, and foreign keys.
6. Additional auto-merge incompatibility discovered by PM9 tests: Android's task-local loop stack contains a `ContextVar`, while PM9 structured forks deep-copy the stack. Materialize the current branch's list before deep copy at the sole copy caller. This preserves each side's isolation contract and avoids copying execution context internals.
7. Android debug test previously expected a subflow scope without PM9 call identity fields. Its assertion now checks `callNodeId` and the exact parent `executionId` in `callVisitId`, retaining debug scope/loop expectations.

## Observed red evidence

- `backend-initial-red.log`: existing unresolved conflict markers caused two pytest collection syntax errors (Android runtime and worker protocol).
- `backend-migration-red.log`: one failed head assertion, one passed historical revision hash test; observed two heads.
- `backend-migration-upgrade-red.log`: 3 failed / 1 passed; both real previous-head upgrade tests raised Alembic `MultipleHeads` before the merge revision existed.
- `backend-focused.log`: 139 passed / 1 failed / 1 dependency warning in 50.80s. Failure: `test_real_worker_runs_to_node_inside_canvas_subflow_with_scope`, stale scope expectation described above.
- `backend-runtime-green.log` (first rerun, filename retained): 44 passed / 9 failed / 1 dependency warning in 10.89s. Existing PM9 structured-fork tests reproduced `TypeError: cannot pickle '_contextvars.ContextVar' object`; associated manual queue tests timed out because fork construction failed. All nine are covered by the final runtime run.
- `backend-ruff.log`: 3 import-only merge findings; corrected imports, not suppressed.

## Confirmed green verification

Commands below run from `apps/backend` with explicit `PYTHONPATH=src`.

- `python -m compileall -q apps/backend/src` from repo root: pass; spec `compile(..., 'exec')`: pass.
- `.venv/bin/ruff check src tests`: **All checks passed** (`backend-ruff-final.log`).
- `.venv/bin/python -m pytest tests/unit/test_project_graph_executor.py tests/unit/workflows/test_runtime_control_flow_core.py tests/unit/workflows/test_debug_runtime_control.py tests/contract/test_studio_variable_tracking.py tests/integration/test_migration_heads.py -q`: **52 passed**, one upstream Starlette/AnyIO deprecation warning, **1.21s** (`backend-runtime-final.log`).
- `.venv/bin/python -m pytest tests/integration/test_*migration*.py tests/integration/test_database_compatibility_inspector.py tests/integration/test_custom_module_revision_compatibility.py tests/integration/test_workflow_recordings.py tests/integration/test_android*.py tests/unit/test_android*.py -q`: **559 passed**, two warnings, **81.57s** (`backend-android-migrations-green.log`). Warnings: upstream Starlette/AnyIO alias and intentional duplicate-manifest APK fixture.
- `git diff --cached --check -- apps/backend`: pass; no unresolved backend paths remain.

- `.venv/bin/python -m pytest tests/integration/test_workflow_worker_protocol.py -q`: **24 passed in 48.82s**, no warnings (`backend-worker-final.log`).

Full backend/frontend, type checks, OpenAPI, and native packaging acceptance remain parent-owned and are not implied by these scoped results.
