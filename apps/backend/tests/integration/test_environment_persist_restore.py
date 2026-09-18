"""Real CloakBrowser persist/restore. Skips unless AUTOFLOW_TEST_CLOAKBROWSER is set."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest

from autoflow.providers.browser.persistent_context import launch_persistent_instance
from tests.contract.test_project_environments import PROFILE, _project, make
from tests.fixtures.login_site import LoginSite

COMMAND = {
    "fingerprintSeed": 31415,
    "expertArgs": [],
    "humanPreset": "default",
    "browserVersion": "146.0.1",
    "releaseChannel": "stable",
    "geoip": False,
    "humanize": False,
}


@pytest.fixture
def real_persist_browser(monkeypatch):
    configured = os.environ.get("AUTOFLOW_TEST_CLOAKBROWSER")
    if not configured:
        pytest.skip("set AUTOFLOW_TEST_CLOAKBROWSER to an installed real CloakBrowser executable")
    executable = Path(configured).resolve(strict=True)
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(executable))
    source = next(parent for parent in executable.parents if parent.name.startswith("chromium-"))
    command = {
        **COMMAND,
        "browserVersion": source.name.removeprefix("chromium-"),
        "executablePath": str(executable),
    }
    site = LoginSite().start()
    try:
        yield executable, command, site
    finally:
        site.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("via_end", [False, True], ids=["explicit-close", "http-end-close"])
async def test_real_login_persists_after_browser_close(tmp_path, real_persist_browser, via_end):
    _executable, command, site = real_persist_browser
    _client, projects, service = make(tmp_path)
    project_id = _project(projects)
    instance = service.reserve(
        project_id,
        service.resolve(project_id, {"source": "newFromProfile", "profileId": PROFILE}),
        task_id=str(uuid4()),
        run_id=str(uuid4()),
        holder_kind="task",
        holder_id=str(uuid4()),
    )
    work = service.instance_path(instance.instance_id)
    context = await launch_persistent_instance(work, command, headless=True)
    try:
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(site.url, wait_until="domcontentloaded")
        await page.fill("#user", "demo")
        await page.fill("#password", "pass")
        await page.click("#submit")
        await page.wait_for_function("document.querySelector('#status')?.textContent === '已登录'")
        cookies = await context.cookies()
        assert any(item.get("name") == "autoflow_login" for item in cookies)
        await context.storage_state()
        if via_end:
            loop = asyncio.get_running_loop()

            def close_browser(_service, owned_instance):
                assert owned_instance.instance_id == instance.instance_id
                asyncio.run_coroutine_threadsafe(context.close(), loop).result(timeout=20)

            service._closer = close_browser
            response = await asyncio.to_thread(
                _client.post,
                f"/api/v1/projects/{project_id}/tasks/{instance.active_task_id}/end",
                headers={"Idempotency-Key": str(uuid4())},
                json={
                    "taskId": instance.active_task_id, "runId": instance.active_run_id,
                    "instanceId": instance.instance_id, "expectedUseGeneration": 1,
                    "executionGeneration": 1,
                    "retainEnvironment": {"enabled": True, "mode": "saveAs", "name": "真实登录环境"},
                },
            )
            assert response.status_code == 202
            saved = response.json()["outcome"]
    finally:
        await context.close()
    if not via_end:
        service.environments.set_instance_state(instance.instance_id, "closed")
    for _ in range(50):
        if not (work / "SingletonLock").exists():
            break
        await asyncio.sleep(0.1)
    saved = saved if via_end else service.save(
        project_id,
        str(uuid4()),
        {
            "instanceId": instance.instance_id,
            "mode": "save_as",
            "expectedUseGeneration": 1,
            "executionGeneration": 1,
            "name": "真实登录环境",
        },
    )[0]
    assert saved["phase"] == "completed"
    service.close_instance(project_id, instance.instance_id, None)
    restored = service.reserve(
        project_id,
        service.resolve(
            project_id,
            {"source": "fixedEnvironment", "environmentId": saved["saved"]["environmentId"]},
        ),
        task_id=str(uuid4()),
        run_id=str(uuid4()),
        holder_kind="task",
        holder_id=str(uuid4()),
    )
    again = await launch_persistent_instance(
        service.instance_path(restored.instance_id), command, headless=True
    )
    try:
        page = again.pages[0] if again.pages else await again.new_page()
        await page.goto(site.url + "me", wait_until="domcontentloaded")
        assert await page.inner_text("body") == "已登录"
    finally:
        await again.close()
