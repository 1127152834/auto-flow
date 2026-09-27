"""Run the original real-browser scenario with correct lifecycle calls in memory.

This diagnostic does not edit the original test or replace its recorded failure.
Its input remains the original synthetic HTML fixture, using the real browser.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
import time


def main() -> None:
    root = Path(__file__).resolve().parents[4]
    backend = root / "apps" / "backend"
    sys.path[:0] = [str(backend), str(backend / "src")]
    source_path = backend / "tests/integration/test_workflow_real_cloakbrowser.py"
    source = source_path.read_text()
    for variable in ("app", "restored"):
        before = f"await {variable}.router.on_shutdown[-1]()"
        assert source.count(before) == 1
        source = source.replace(before, f"await run_registered_shutdown({variable})")
    async def run_registered_shutdown(app):
        for callback in app.router.on_shutdown:
            result = callback()
            if inspect.isawaitable(result):
                await result

    namespace = {
        "__file__": str(source_path),
        "__name__": "qa_recreation_diagnostic",
        "run_registered_shutdown": run_registered_shutdown,
    }
    exec(compile(source, str(source_path), "exec"), namespace)
    from tests.fixtures.profiles import valid_profile_values

    temporary = Path(tempfile.mkdtemp(prefix="autoflow-audit-recreation-cleanup-"))
    os.environ["CLOAKBROWSER_CACHE_DIR"] = str(temporary / "browser-cache")
    fixture = namespace["real_cloak_page"].__wrapped__()
    page = next(fixture)
    started = time.monotonic()
    try:
        asyncio.run(namespace[
            "test_real_cloakbrowser_persisted_dispatch_and_service_recreation"
        ](temporary, valid_profile_values.__wrapped__(), page))
    finally:
        fixture.close()
    print(json.dumps({
        "passed": True,
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "workspace": str(temporary),
        "source": str(source_path),
        "changesInMemoryOnly": [
            "app: call all registered shutdown callbacks, awaiting awaitable results",
            "restored: call all registered shutdown callbacks, awaiting awaitable results",
        ],
        "originalScenarioAssertions": "all passed, including service recreation",
        "dataProvenance": "original synthetic HTML fixture, real CloakBrowser and SQLite",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
