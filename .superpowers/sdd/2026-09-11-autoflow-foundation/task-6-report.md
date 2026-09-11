# Task 6 report — OpenAPI generation, sidecar smoke, and CI

## Scope

Implemented the cross platform foundation checks only:

- Exported the FastAPI `/openapi.json` contract and generated the desktop TypeScript contract with `openapi-typescript`.
- Added deterministic `openapi:generate` and `openapi:check` commands.
- Added a development sidecar smoke command that reads `AUTOFLOW_READY`, checks `/health` with the instance token, and terminates the process.
- Added a Windows and macOS CI matrix for Python, npm, OpenAPI, smoke, lint, typecheck, tests, build, Ruff, and mypy.

No WebRPA runtime or integration was added. Remote CI was not run from this checkout.

## TDD and verification

The pre-implementation smoke/generation commands failed because the scripts and generated contract did not exist. After implementation:

- `npm run openapi:generate` — passed.
- `npm run openapi:check` — passed with no generated diff.
- `npm run typecheck` — passed.
- `npm test` — passed, 15 tests.
- `npm run lint` — passed; ESLint emitted an existing module type warning.
- `npm run build` — passed.
- `uv run --directory apps/backend ruff check .` — passed.
- `uv run --directory apps/backend mypy src` — passed.
- `uv run --directory apps/backend pytest -q` — passed, 11 tests; existing dependency deprecation warnings only.
- `npm run smoke:sidecar` — passed; development sidecar became ready, health metadata matched, and the child exited during cleanup.
- `npm run test:structure` — passed, 3 tests.

The CI workflow is declarative and has not been represented as a remote job result.
