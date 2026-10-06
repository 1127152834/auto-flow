"""G1 accounts (remediation M4 S10; AC4-01, AC4-02): every row logs in as its own identity.

Each data row is an account with its own identity (created and linked from the rows). Three
cycles log every account in; 2% of the accounts have a wrong password. The profile page reports
what the site saw — user agent, timezone, cookie and a canvas fingerprint — and the row records it.
Checks: identities' seeds are pairwise distinct; each identity is identical across its three
runs and differs from the others; wrong passwords end as business failures without stopping the
batch, are skipped in later cycles and count against the identity.
The exit lookup is stubbed as "unlocated" (warn and continue): the scenario must not depend on
public echo services; the 60 s cycle cooldown is set to zero. Run: pytest -m golden tests/golden/test_g1_accounts.py -o faulthandler_timeout=0
"""

from __future__ import annotations

import asyncio
import html
import os
import shutil
import socket
import threading
from collections import Counter
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
import uvicorn

from autoflow.application.workflows import browser_resources
from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.profiles.models import ProfileSpec
from autoflow.domain.project_runs import ledger
from autoflow.infrastructure.database.identity_models import (
    IdentityRow,
    SeedRegistryRow,
)
from tests.integration.test_project_input_groups import _empty_table, uid

from .harness import flow_node

pytestmark = [pytest.mark.golden, pytest.mark.asyncio]

ROWS = int(os.environ.get("AUTOFLOW_G1_ROWS", "30"))
CYCLES = 3
CONCURRENCY = 2
TIMEZONES = ("Asia/Shanghai", "Europe/Berlin", "America/New_York")
TERMINAL = {"completed", "failed", "interrupted", "stopped"}

PROFILE_PAGE = """<!doctype html><title>资料</title><script>
const c = document.createElement('canvas'); c.width = 200; c.height = 40;
const g = c.getContext('2d'); g.font = '14px Arial'; g.fillStyle = '#c60'; g.fillRect(4, 4, 80, 20);
g.fillStyle = '#068'; g.fillText('G1 账号 fingerprint', 6, 22);
let h = 0; for (const ch of c.toDataURL()) h = (h * 31 + ch.charCodeAt(0)) | 0;
const fp = [navigator.userAgent,
  Intl.DateTimeFormat().resolvedOptions().timeZone, document.cookie, (h >>> 0).toString(16), '__IP__'].join('|');
fetch('/report?fp=' + encodeURIComponent(fp)).finally(() => {
  const shown = document.createElement('p'); shown.id = 'fp'; shown.textContent = fp; document.body.append(shown);
});
</script>"""


class AccountSite:
    """/login checks the password (accounts in ``wrong`` always fail); /profile reports what it saw."""

    def __init__(self, wrong: set[str]) -> None:
        self.wrong = wrong
        self.logins: Counter[str] = Counter()
        self.reports: dict[str, list[str]] = {}  # what each visit of /profile saw, by session cookie
        self._lock = threading.Lock()
        site = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                return None

            def _send(self, body: str, cookie: str | None = None) -> None:
                content = body.encode("utf-8")
                with suppress(BrokenPipeError, ConnectionResetError):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    if cookie:
                        self.send_header("Set-Cookie", cookie)
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)

            def do_GET(self) -> None:
                url = urlsplit(self.path)
                query = {key: values[0] for key, values in parse_qs(url.query).items()}
                if url.path == "/login":
                    account = query.get("account", "")
                    with site._lock:
                        site.logins[account] += 1
                    if account in site.wrong or query.get("password") != f"pw-{account}":
                        self._send("<p id=result>密码错误</p>")
                    else:
                        self._send("<p id=result>ok</p>", cookie=f"session={html.escape(account)}; Path=/")
                elif url.path == "/report":
                    cookie = self.headers.get("Cookie", "")
                    account = cookie.split("session=", 1)[1].split(";")[0] if "session=" in cookie else ""
                    with site._lock:
                        site.reports.setdefault(account, []).append(query.get("fp", ""))
                    self._send("ok")
                elif url.path == "/profile":
                    self._send(PROFILE_PAGE.replace("__IP__", self.client_address[0]))
                else:
                    self._send("not found")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def _binding(project_id: str, table: dict, field_id: str, alias: str) -> dict:
    return {
        "inputFieldId": uid(), "inputFieldAlias": alias,
        "fieldRef": {"projectId": project_id, "tableId": table["tableId"], "datasetGeneration": table["datasetGeneration"], "fieldId": field_id},
    }


async def test_accounts_run_as_their_own_identities(tmp_path, valid_profile_values, real_cloak_page, monkeypatch):
    executable, _, _ = real_cloak_page
    kernel = next(parent for parent in executable.parents if parent.name.startswith("chromium-"))
    monkeypatch.setattr(browser_resources, "_locate_exit_with_geoip", lambda _url: (None, None))
    monkeypatch.setattr(ledger, "CYCLE_REUSE_SECONDS", 0)  # the next cycle may claim a row at once
    accounts = [f"acct-{index:04}" for index in range(ROWS)]
    step = max(1, ROWS // max(1, ROWS // 50))  # 2% of the accounts, at least one
    wrong = {account for index, account in enumerate(accounts) if index % step == step // 2}
    await asyncio.to_thread(shutil.copytree, kernel, tmp_path / "data" / "kernels" / kernel.name, symlinks=True)
    app = create_app(Settings(data_dir=str(tmp_path), instance_id="g1", instance_token="g1-token"))
    server = uvicorn.Server(uvicorn.Config(app, lifespan="off", access_log=False, log_level="warning"))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server_task = None
    site = AccountSite(wrong)
    try:
        profile = app.state.profile_service.create(ProfileSpec.from_values(
            {**valid_profile_values, "headless": True, "browser_version": kernel.name.removeprefix("chromium-")}))
        await app.state.project_workflow_dispatcher.startup()
        await app.state.project_run_scheduler.startup()
        server_task = asyncio.create_task(server.serve(sockets=[listener]))
        async with asyncio.timeout(10):
            while not server.started:
                await asyncio.sleep(0.01)
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{listener.getsockname()[1]}",
            headers={"x-autoflow-token": "g1-token"}, trust_env=False, timeout=60,
        ) as client:

            async def api(method, path, body=None, status=200):
                response = await client.request(method, path, json=body, headers={"Idempotency-Key": str(uuid4())})
                assert response.status_code == status, f"{method} {path}: {response.status_code} {response.text}"
                return response.json()

            project = await api("POST", "/api/v1/projects", {"name": "G1 账号", "description": ""}, 201)
            project_id = project["projectId"]
            prefix = f"/api/v1/projects/{project_id}"
            factory = app.state.session_factory
            table, key_field = _empty_table(factory, project_id, "账号")
            fields = {}
            for revision, (key, name) in enumerate((("password", "密码"), ("fingerprint", "指纹")), start=2):
                fields[key] = (await api("POST", prefix + f"/tables/{table['tableId']}/fields", {
                    "definition": {"key": key, "name": name, "type": "string", "required": False, "validation": {}},
                    "sourceColumnPolicy": "localOnly", "expectedTableRevision": revision,
                }))["field"]["ref"]["fieldId"]
            records = {}
            for account in accounts:
                created = await api("POST", prefix + f"/tables/{table['tableId']}/records", {
                    "datasetGeneration": table["datasetGeneration"],
                    "values": [{"fieldId": key_field["ref"]["fieldId"], "value": account}, {"fieldId": fields["password"], "value": f"pw-{account}"}],
                }, 201)
                records[account] = created["ref"]
            batch = await api("POST", prefix + "/identities/from-records", {
                "tableId": table["tableId"], "datasetGeneration": table["datasetGeneration"], "templateProfileId": profile.id,
                "rows": [{"recordKey": ref["recordKey"]["value"], "keyType": ref["recordKey"]["type"], "name": account} for account, ref in records.items()],
            })
            assert batch["created"] == ROWS and all(item["linked"] for item in batch["identities"])
            identity_of = {item["recordKey"]: item["identityId"] for item in batch["identities"]}
            with factory() as session:  # each identity its own timezone (rotating three regions)
                for index, identity_id in enumerate(identity_of.values()):
                    session.get(IdentityRow, identity_id).region = {"timezone": TIMEZONES[index % len(TIMEZONES)]}
                session.commit()

            account_binding = _binding(project_id, table, key_field["ref"]["fieldId"], "账号")
            password_binding = _binding(project_id, table, fields["password"], "密码")
            # The written field is read too: R2-24 only lets a Task overwrite a value it has seen.
            fingerprint_binding = _binding(project_id, table, fields["fingerprint"], "指纹")
            input_spec = {
                "inputId": uid(), "alias": "账号", "tableId": table["tableId"], "datasetGeneration": table["datasetGeneration"],
                "mode": "independent", "required": True, "fieldBindings": [account_binding, password_binding, fingerprint_binding],
                "filter": {"type": "all", "items": []}, "orderBy": [{"systemField": "recordKey", "direction": "asc"}],
            }
            value = lambda binding: "{PROJECT_INPUTS['" + input_spec["inputId"] + "']['values']['" + binding["inputFieldId"] + "']}"
            record_ref = "{PROJECT_INPUTS['" + input_spec["inputId"] + "']['recordRef']}"
            nodes = [
                flow_node("login", "open_page", 0, url=f"{site.base_url}/login?account={value(account_binding)}&password={value(password_binding)}", timeout=15),
                flow_node("result", "get_element_info", 1, selector="#result", attribute="text", variableName="login", timeout=5),
                flow_node("check", "condition", 2, leftValue="{login}", rightValue="ok"),
                flow_node("profile", "open_page", 3, url=f"{site.base_url}/profile", timeout=15),
                flow_node("read", "get_element_info", 4, selector="#fp", attribute="text", variableName="fp", timeout=5),
                flow_node("write", "project_data", 5, operation="updateRecord", bindingProjectId=project_id, variableName="written",
                          arguments={"recordRef": record_ref, "changes": {fields["fingerprint"]: "{fp}"}},
                          tableGrant={"tableId": table["tableId"], "datasetGeneration": table["datasetGeneration"],
                                      "operations": ["updateRecord"], "fieldIds": [fields["fingerprint"]], "readPurposes": []}),
                flow_node("logged-in", "set_variable", 6, variableName="outcome", variableValue="succeeded"),
                flow_node("refused", "set_variable", 7, variableName="outcome", variableValue="failed"),
                # One End for every branch; the login outcome decides the business result (M4 R4-07).
                flow_node("end", "project_end", 8, businessResult="{outcome}", retainEnvironment=False),
            ]
            edges = [
                {"id": "e1", "source": "login", "target": "result"},
                {"id": "e2", "source": "result", "target": "check"},
                {"id": "ok", "source": "check", "target": "profile", "sourceHandle": "true"},
                {"id": "no", "source": "check", "target": "refused", "sourceHandle": "false"},
                {"id": "e3", "source": "profile", "target": "read"},
                {"id": "e4", "source": "read", "target": "write"},
                {"id": "e5", "source": "write", "target": "logged-in"},
                {"id": "e6", "source": "logged-in", "target": "end"},
                {"id": "e7", "source": "refused", "target": "end"},
            ]
            automation = await api("POST", prefix + "/automations", {
                "name": "G1 账号登录", "description": "", "parameterSchema": [],
                "inputPlan": {"inputs": [input_spec]},
                "environmentPolicy": {"source": "inputIdentity", "inputId": input_spec["inputId"], "profileId": profile.id,
                                      "proxyOverride": {"mode": "none"}, "modelProviderId": None},
                "runPolicy": {
                    "maxTasks": min(ROWS, 100), "concurrency": CONCURRENCY, "maxLiveInstances": CONCURRENCY,
                    "continueAfterFailure": True, "automaticExecutionTimeoutSeconds": 60, "manualDeadlineSeconds": 120,
                    "claimMode": "cycle", "failurePolicy": "thresholds", "retryBudget": 1,
                },
            }, 201)
            workflow_path = f"/api/workflows/{automation['workflowId']}"
            workflow = await api("GET", workflow_path)
            workflow.pop("browserEnvironmentVersion", None)  # the browser comes from the identity, not a node
            await api("PUT", workflow_path, {**workflow, "clientRequestId": str(uuid4()), "expectedRevision": workflow["revision"], "nodes": nodes, "edges": edges})
            automation_path = prefix + f"/automations/{automation['automationId']}"
            for _cycle in range(CYCLES):
                accepted = await api("POST", automation_path + "/batches", {
                    "expectedAutomationRevision": automation["managementRevision"], "parameters": {},
                    # A task limit is at most 100; beyond that one batch per cycle takes every row (unlimited).
                    "maxTasks": None if ROWS > 100 else ROWS, "concurrency": CONCURRENCY, "executionMode": "realWrites",
                }, 202)
                batch_path = prefix + f"/batches/{accepted['operation']['result']['batch']['batchId']}"
                async with asyncio.timeout(1800):
                    while (current := (await api("GET", batch_path))["batch"])["status"] not in TERMINAL:
                        assert current["status"] != "paused", current  # business failures never pause the batch
                        await asyncio.sleep(0.5)
        with factory() as session:
            seeds = dict(session.query(IdentityRow.id, SeedRegistryRow.seed_value).join(SeedRegistryRow, SeedRegistryRow.id == IdentityRow.seed_id).all())
            health = {row.id: row.health for row in session.query(IdentityRow).all()}
    finally:
        site.close()
        await app.state.project_run_scheduler.shutdown()
        await app.state.project_workflow_dispatcher.shutdown()
        server.should_exit = True
        if server_task is not None:
            await server_task
        listener.close()

    # AC4-01: new identities never share a seed; each account looks the same every time, unlike the others.
    assert len(set(seeds.values())) == ROWS
    good = [account for account in accounts if account not in wrong]
    seen = {account: site.reports.get(account, []) for account in accounts}
    for account in good:
        runs = seen[account]
        assert len(runs) == CYCLES and len(set(runs)) == 1, (account, runs)
        _user_agent, timezone, cookie, _canvas, ip = runs[0].split("|")
        assert timezone == TIMEZONES[accounts.index(account) % len(TIMEZONES)]
        assert cookie == f"session={account}" and ip == "127.0.0.1"
    canvases = {seen[account][0].split("|")[3] for account in good}
    assert len(canvases) == len(good), "each identity draws its own canvas"
    # AC4-02: wrong passwords are business failures; the batch went on and the identity counts them.
    for account in wrong:
        # A business failure skips the row in later cycles (ledger R2-14) and counts once against the identity.
        assert not seen[account]
        assert health[identity_of[records[account]["recordKey"]["value"]]]["consecutiveFailures"] == 1
        assert site.logins[account] == 1
    for account in good:
        assert health[identity_of[records[account]["recordKey"]["value"]]]["consecutiveFailures"] == 0
