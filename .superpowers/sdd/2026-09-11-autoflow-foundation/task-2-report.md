# Task 2 report

## RED

Command:

```text
uv --directory apps/backend run pytest tests/unit/test_ready.py tests/unit/test_health.py -q
```

Result: collection failed as expected with `ModuleNotFoundError: No module named 'autoflow'` for both requested tests.

## GREEN

Commands:

```text
uv --directory apps/backend run pytest tests/unit/test_ready.py tests/unit/test_health.py tests/unit/test_config.py tests/unit/test_token.py -q
uv --directory apps/backend run pytest -q
```

Results: focused tests passed (`4 passed`, 2 existing dependency deprecation warnings); complete backend suite passed (`4 passed`, 2 warnings).

An additional subprocess check started `python -m autoflow --port 0`, parsed a non-zero `AUTOFLOW_READY` port, fetched `/health`, and confirmed an unauthenticated `/api/v1/*` request returned 401.

## Files

- Added the `autoflow` package, `Settings`, FastAPI app factory, health router, ready-line serializer, and Uvicorn CLI entry point.
- Added config, health, ready, and token unit tests.
- Added package and pytest source-layout configuration in `apps/backend/pyproject.toml` and refreshed its lock metadata.

## Self-review

The implementation keeps startup output in `__main__.py`; routes never emit readiness text. The instance token is read from `AUTOFLOW_INSTANCE_TOKEN` and is never included in logs or readiness JSON. Socket pre-binding makes port 0 resolution deterministic before Uvicorn starts.

## Concerns

No unresolved implementation concerns. The suite emits upstream Starlette/httpx deprecation warnings that are unrelated to this change.
