# Task 5 report — cross-platform path service and startup configuration

## Scope

Implemented Task 5 only:

- Added backend `AppPaths` for injected absolute data directories.
- Centralized backend directory creation in bootstrap startup.
- Required `--data-dir` for standalone backend startup.
- Added desktop backend environment resolution from Electron `userData`.
- Passed the same data directory to the sidecar through CLI args and `AUTOFLOW_DATA_DIR`.

No WebRPA runtime or integration code was added.

## TDD evidence

RED:

- `uv run pytest tests/unit/test_paths.py tests/unit/test_main.py -q`
  - Failed with `ModuleNotFoundError: No module named 'autoflow.infrastructure'`.
- `npm --workspace @autoflow/desktop test -- src/main/platform/paths.test.ts`
  - Failed with `resolveBackendEnvironment is not a function`.

GREEN:

- `uv run pytest -q`
  - `11 passed, 2 warnings`
- `npm --workspace @autoflow/desktop test -- src/main/platform/paths.test.ts src/main/sidecar/supervisor.test.ts`
  - `2 passed`, `8 tests passed`
- `npm --workspace @autoflow/desktop run typecheck`
  - Passed

## Notes

The backend now rejects relative data directories through `AppPaths.from_data_dir()` and the standalone CLI requires `--data-dir`. Electron injects `app.getPath('userData')` into the supervisor and the supervisor forwards it consistently as both `--data-dir` and `AUTOFLOW_DATA_DIR`.
