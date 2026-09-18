#!/usr/bin/env python
"""PM5 first demonstrable chain at the management HTTP + real browser layer.

Real in this probe:
  * the production ``create_app`` wiring (routes, services, SQLite, migrations)
  * a real CloakBrowser process launched by ``EnvironmentBrowserLauncher.opener``
    on the instance work copy, driven through a local login site
  * ``POST /tasks/{taskId}/end`` retaining the environment and linking the
    account record, ending with the real ``closer`` and a saved directory
  * a second instance reserved from ``fixedEnvironment`` that must still be
    signed in

Not real in this probe: Electron renderer clicks (separate QA harness) and the
production workflow executor.  Results are written next to the screenshots as
JSON so the report can separate the two evidence classes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "apps" / "backend"))
sys.path.insert(0, str(REPO / "apps" / "backend" / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from autoflow.bootstrap.app import create_app  # noqa: E402
from autoflow.bootstrap.config import Settings  # noqa: E402
from autoflow.domain.kernels.models import InstalledKernel  # noqa: E402
from autoflow.providers.browser.persistent_context import (  # noqa: E402
    persistent_launch_kwargs,
)
from tests.fixtures.login_site import LoginSite  # noqa: E402
from tests.fixtures.model_management import (  # noqa: E402
    FakeCredentialStore,
    FakeModelGateway,
)

DEFAULT_KERNEL = (
    Path.home()
    / "Library/Application Support/@autoflow/desktop/data/kernels"
    / "chromium-145.0.7632.109.2/Chromium.app/Contents/MacOS/Chromium"
)


class InstalledKernels:
    """Minimal kernel lookup: the catalog is stubbed, the browser is real."""

    def __init__(self, kernel: Path, version: str) -> None:
        self.kernel = kernel
        self.version = version

    def installed(self) -> list[InstalledKernel]:
        return [InstalledKernel("public", self.version, self.kernel, 1)]

    def is_installed(self, edition: str, version: str) -> bool:
        return edition == "public" and version == self.version


def key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid4())}


def login_in_context(launcher, instance_id: str, url: str) -> dict:
    """Drive the exact context the production opener launched."""

    context = launcher._contexts[instance_id]  # noqa: SLF001 -- QA owns the process
    owner = launcher._owner_loop()  # noqa: SLF001 -- must stay on the launch loop

    async def sign_in():
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        await page.fill("#user", "demo")
        await page.fill("#password", "pass")
        await page.click("#submit")
        await page.wait_for_function(
            "document.querySelector('#status')?.textContent === '已登录'",
            timeout=20_000,
        )
        cookies = await context.cookies()
        return {
            "signedIn": True,
            "cookieNames": sorted({item.get("name", "") for item in cookies}),
        }

    return owner.run(sign_in(), timeout=90)


def read_status(launcher, instance_id: str, url: str) -> dict:
    context = launcher._contexts[instance_id]  # noqa: SLF001 -- QA owns the process
    owner = launcher._owner_loop()  # noqa: SLF001 -- must stay on the launch loop

    async def status():
        page = context.pages[0] if context.pages else await context.new_page()
        response = await page.goto(url, wait_until="domcontentloaded")
        body = await page.evaluate("document.body ? document.body.innerText : ''")
        return {"httpStatus": response.status if response else None, "body": body.strip()}

    return owner.run(status(), timeout=90)


def mark_new_content(launcher, instance_id: str, url: str) -> dict:
    """Change persistent browser state so a later read can prove it was saved."""

    context = launcher._contexts[instance_id]  # noqa: SLF001 -- QA owns the process
    owner = launcher._owner_loop()  # noqa: SLF001 -- must stay on the launch loop

    async def write_marker():
        page = context.pages[0] if context.pages else await context.new_page()
        if page.url != url:
            await page.goto(url, wait_until="domcontentloaded")
        await page.evaluate(
            "() => { document.cookie = 'pm5_marker=v2; Path=/; Max-Age=86400';"
            " window.localStorage.setItem('pm5_note', 'v2'); }"
        )
        cookies = await context.cookies()
        return {
            "cookieWritten": any(
                item.get("name") == "pm5_marker" and item.get("value") == "v2"
                for item in cookies
            ),
            "localStorageWritten": await page.evaluate(
                "() => window.localStorage.getItem('pm5_note')"
            ),
        }

    return owner.run(write_marker(), timeout=90)


def read_marked_content(launcher, instance_id: str, url: str) -> dict:
    context = launcher._contexts[instance_id]  # noqa: SLF001 -- QA owns the process
    owner = launcher._owner_loop()  # noqa: SLF001 -- must stay on the launch loop

    async def read():
        page = context.pages[0] if context.pages else await context.new_page()
        response = await page.goto(url, wait_until="domcontentloaded")
        body = await page.evaluate("document.body ? document.body.innerText : ''")
        cookies = await context.cookies()
        return {
            "httpStatus": response.status if response else None,
            "body": body.strip(),
            "marker": next(
                (
                    item.get("value")
                    for item in cookies
                    if item.get("name") == "pm5_marker"
                ),
                None,
            ),
            "note": await page.evaluate("() => window.localStorage.getItem('pm5_note')"),
        }

    return owner.run(read(), timeout=90)


def wait_for_release(store, instance_id: str, seconds: float = 20) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not store.runtime_lock_present(instance_id):
            return True
        time.sleep(0.2)
    return not store.runtime_lock_present(instance_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, help="isolated data dir for this run")
    parser.add_argument("--out", required=True, help="evidence directory for the JSON result")
    parser.add_argument("--kernel", default=str(DEFAULT_KERNEL))
    parser.add_argument(
        "--keep-browser",
        action="store_true",
        help="leave the resumed browser open for a human to inspect",
    )
    args = parser.parse_args()

    kernel = Path(args.kernel).expanduser().resolve(strict=True)
    version = next(
        parent.name.removeprefix("chromium-")
        for parent in kernel.parents
        if parent.name.startswith("chromium-")
    )
    workspace = Path(args.workspace).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("CLOAKBROWSER_BINARY_PATH", str(kernel))
    site = LoginSite().start()
    report: dict = {
        "scenario": "PM5 首条链：真实浏览器登录 → End 保留并关联 → 关闭 → 恢复登录",
        "evidenceType": "production 装配下的管理 HTTP + 真实 CloakBrowser",
        "notEvidence": ["Electron 渲染层点击", "生产工作流执行节点推进"],
        "kernel": str(kernel),
        "kernelVersion": version,
        "workspace": str(workspace),
        "steps": [],
    }
    app = None
    client = None
    try:
        app = create_app(
            Settings(
                data_dir=str(workspace),
                instance_id="pm5-browser-chain",
                instance_token="renderer",
                host_token="host",
            ),
            installed_kernel_lookup=InstalledKernels(kernel, version),
            credential_store=FakeCredentialStore(),
            model_gateway=FakeModelGateway(),
        )
        client = TestClient(app)
        client.__enter__()
        client.headers["x-autoflow-token"] = "renderer"

        project = client.post(
            "/api/v1/projects", headers=key(), json={"name": "PM5 首条链"}
        ).json()
        project_id = project["projectId"]
        table = client.post(
            f"/api/v1/projects/{project_id}/tables", headers=key(), json={"name": "账号"}
        ).json()
        table_id = table["tableId"]
        generation = table["datasetGeneration"]
        field = client.post(
            f"/api/v1/projects/{project_id}/tables/{table_id}/fields",
            headers=key(),
            json={
                "definition": {
                    "key": "account.name",
                    "name": "账号名称",
                    "type": "string",
                    "required": True,
                    "validation": {},
                },
                "expectedTableRevision": 1,
                "sourceColumnPolicy": "localOnly",
            },
        ).json()
        field_id = field["field"]["ref"]["fieldId"]
        record = client.post(
            f"/api/v1/projects/{project_id}/tables/{table_id}/records",
            headers=key(),
            json={
                "datasetGeneration": generation,
                "values": [{"fieldId": field_id, "value": "主账号"}],
            },
        ).json()
        record_ref = record["ref"]
        report["projectId"] = project_id
        report["tableId"] = table_id
        report["recordRef"] = record_ref
        report["linkRevision"] = record["linkRevision"]
        report["steps"].append(
            {"step": "HTTP 建项目 / 账号表 / 必填字段 / 记录", "ok": True}
        )

        profile = client.post(
            "/api/v1/profiles",
            json={
                "name": "PM5 首条链配置",
                "startUrl": "about:blank",
                "browserVersion": version,
                "browserEdition": "public",
                "releaseChannel": "stable",
                "humanPreset": "default",
            },
        ).json()
        report["profileId"] = profile["id"]

        service = app.state.environment_service
        launcher = app.state.environment_browser
        task_id = str(uuid4())
        run_id = str(uuid4())
        instance = service.reserve(
            project_id,
            service.resolve(
                project_id, {"source": "newFromProfile", "profileId": profile["id"]}
            ),
            task_id=task_id,
            run_id=run_id,
            holder_kind="task",
            holder_id=str(uuid4()),
        )
        opened = client.post(
            f"/api/v1/projects/{project_id}/environment-instances/{instance.instance_id}/open",
            headers=key(),
            json={"expectedUseGeneration": 1},
        )
        report["openStatus"] = opened.status_code
        report["openBody"] = opened.json() if opened.content else {}
        report["steps"].append(
            {
                "step": "POST environment-instances/open 触发真实 opener",
                "ok": opened.status_code == 202,
                "launched": opened.json()["outcome"]["launched"] if opened.status_code == 202 else None,
            }
        )
        if opened.status_code != 202:
            report["passed"] = False
            report["blockedAt"] = "open"
            return finish(report, out, app, service, launcher, None)

        signed_in = login_in_context(launcher, instance.instance_id, site.url)
        report["login"] = signed_in
        report["steps"].append({"step": "在 opener 打开的真实浏览器里登录", **signed_in})

        ended = client.post(
            f"/api/v1/projects/{project_id}/tasks/{task_id}/end",
            headers=key(),
            json={
                "taskId": task_id,
                "runId": run_id,
                "instanceId": instance.instance_id,
                "expectedUseGeneration": 1,
                "executionGeneration": 1,
                "retainEnvironment": {
                    "enabled": True,
                    "mode": "saveAs",
                    "name": "主账号环境",
                    "recordTargets": [
                        {
                            "recordRef": record_ref,
                            "expectedLinkRevision": record["linkRevision"],
                            "replaceAllowed": False,
                        }
                    ],
                },
            },
        )
        body = ended.json() if ended.content else {}
        outcome = body.get("outcome") or {}
        report["endStatus"] = ended.status_code
        report["endPhase"] = outcome.get("phase")
        report["endError"] = body.get("error")
        report["savedEnvironmentId"] = (outcome.get("saved") or {}).get("environmentId")
        report["endTargets"] = outcome.get("targets")
        report["browserClosedByEnd"] = wait_for_release(
            service.store, instance.instance_id
        )
        report["instanceStateAfterEnd"] = service.environments.get_instance(
            project_id, instance.instance_id
        ).state
        report["steps"].append(
            {
                "step": "POST tasks/{taskId}/end 保留环境 + 关联记录",
                "ok": ended.status_code == 202 and outcome.get("phase") == "completed",
                "phase": outcome.get("phase"),
                "targets": outcome.get("targets"),
                "browserClosedByEnd": report["browserClosedByEnd"],
            }
        )
        if not report["savedEnvironmentId"]:
            report["passed"] = False
            report["blockedAt"] = "end"
            return finish(report, out, app, service, None, None)

        environment_id = report["savedEnvironmentId"]
        resumed = service.reserve(
            project_id,
            service.resolve(
                project_id,
                {"source": "fixedEnvironment", "environmentId": environment_id},
            ),
            task_id=str(uuid4()),
            run_id=str(uuid4()),
            holder_kind="task",
            holder_id=str(uuid4()),
        )
        report["resumedInstanceId"] = resumed.instance_id
        report["resumedEnvironmentId"] = environment_id
        reopened = client.post(
            f"/api/v1/projects/{project_id}/environment-instances/{resumed.instance_id}/open",
            headers=key(),
            json={"expectedUseGeneration": 1},
        )
        report["resumeOpenStatus"] = reopened.status_code
        restored = read_status(launcher, resumed.instance_id, f"{site.url}me")
        report["resumeStatus"] = restored
        report["steps"].append(
            {
                "step": "用已保存环境新建实例并重新打开 → 访问 /me",
                "ok": restored["body"] == "已登录",
                "httpStatus": restored["httpStatus"],
                "body": restored["body"],
            }
        )
        if reopened.status_code != 202:
            report["passed"] = False
            report["blockedAt"] = "resume-open"
            return finish(report, out, app, service, launcher, None)

        # The milestone asks for a second save and a third read that sees the
        # newer content, not merely the first restored snapshot.
        marker = mark_new_content(launcher, resumed.instance_id, site.url)
        report["marker"] = marker
        second_end = client.post(
            f"/api/v1/projects/{project_id}/tasks/{resumed.active_task_id}/end",
            headers=key(),
            json={
                "taskId": resumed.active_task_id,
                "runId": resumed.active_run_id,
                "instanceId": resumed.instance_id,
                "expectedUseGeneration": 1,
                "executionGeneration": 1,
                "retainEnvironment": {
                    "enabled": True,
                    "mode": "update",
                    "expectedContentGeneration": 1,
                },
            },
        )
        second_body = second_end.json() if second_end.content else {}
        second_outcome = second_body.get("outcome") or {}
        report["secondSaveStatus"] = second_end.status_code
        report["secondSavePhase"] = second_outcome.get("phase")
        report["secondSaveGeneration"] = (second_outcome.get("saved") or {}).get(
            "contentGeneration"
        )
        report["secondSaveError"] = second_body.get("error")
        report["secondCloseConfirmed"] = wait_for_release(service.store, resumed.instance_id)
        report["steps"].append(
            {
                "step": "修改浏览器状态后 End 更新同一保存环境",
                "ok": second_end.status_code == 202
                and second_outcome.get("phase") == "completed"
                and report["secondSaveGeneration"] == 2,
                "generation": report["secondSaveGeneration"],
                "browserClosedByEnd": report["secondCloseConfirmed"],
            }
        )

        third = service.reserve(
            project_id,
            service.resolve(
                project_id,
                {"source": "fixedEnvironment", "environmentId": environment_id},
            ),
            task_id=str(uuid4()),
            run_id=str(uuid4()),
            holder_kind="task",
            holder_id=str(uuid4()),
        )
        report["thirdInstanceId"] = third.instance_id
        third_open = client.post(
            f"/api/v1/projects/{project_id}/environment-instances/{third.instance_id}/open",
            headers=key(),
            json={"expectedUseGeneration": 1},
        )
        report["thirdOpenStatus"] = third_open.status_code
        third_read = read_marked_content(launcher, third.instance_id, f"{site.url}me")
        report["thirdRead"] = third_read
        report["steps"].append(
            {
                "step": "第三次打开读取新内容",
                "ok": third_read["body"] == "已登录" and third_read["marker"] == "v2",
                "body": third_read["body"],
                "marker": third_read["marker"],
            }
        )
        retained = third if args.keep_browser else None
        report["passed"] = (
            report["login"].get("signedIn") is True
            and report["endStatus"] == 202
            and report["endPhase"] == "completed"
            and report["browserClosedByEnd"] is True
            and restored["body"] == "已登录"
            and report["secondSaveGeneration"] == 2
            and third_read["body"] == "已登录"
            and third_read["marker"] == "v2"
        )
        return finish(report, out, app, service, launcher, retained)
    except BaseException as error:  # noqa: BLE001 -- QA must always dump evidence
        report["passed"] = False
        report["exceptionType"] = type(error).__name__
        report["exception"] = str(error)
        return finish(report, out, app, None, None, None)
    finally:
        site.close()


def finish(report, out, app, service, launcher, keep_instance) -> int:
    if keep_instance is not None and launcher is not None:
        report["keptOpenInstanceId"] = keep_instance.instance_id
    elif launcher is not None:
        try:
            launcher.shutdown()
        except Exception as error:  # noqa: BLE001
            report.setdefault("cleanupWarnings", []).append(str(error))
    report["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "browser-chain.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
