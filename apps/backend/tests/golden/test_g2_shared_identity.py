"""G2 shared accounts (remediation M4 S8; AC4-07): consecutive tasks of one account share its browser directory.

Several rows belong to each account. With ``sessionMode = perIdentity`` the first row of an account logs in
(the site sets a persistent cookie); the account's next rows in the same batch must arrive still logged in,
because they re-attach the held work copy instead of restoring a new one. When the batch ends the login is
saved ONCE per account, and a second batch's first row starts from that saved login.

Checks, per account: first visit has no cookie, later visits have it (batch 1); every visit has it (batch 2);
one instance served all rows of a batch (use generation counts them); one environment saved per account,
one new version per batch; the work copies are gone afterwards; no row ever restored a copy that a
previous task of the same account had written to.
Run: AUTOFLOW_TEST_CLOAKBROWSER=<chrome> pytest -m golden tests/golden/test_g2_shared_identity.py -o faulthandler_timeout=0
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import threading
from collections import defaultdict
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
from autoflow.infrastructure.database.environment_models import (
    ProjectEnvironmentInstanceRow,
    ProjectEnvironmentRow,
)
from autoflow.infrastructure.database.identity_models import IdentityRow
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from tests.integration.test_project_input_groups import _empty_table, uid

from .harness import flow_node

pytestmark = [pytest.mark.golden, pytest.mark.asyncio]

ACCOUNTS = int(os.environ.get("AUTOFLOW_G2_ACCOUNTS", "3"))
ROWS_EACH = int(os.environ.get("AUTOFLOW_G2_ROWS_EACH", "3"))
CONCURRENCY = ACCOUNTS
TERMINAL = {"completed", "failed", "interrupted", "stopped"}


class LoginSite:
    """/visit reports whether the browser still carries the account's login cookie; /login sets it (persistent)."""

    def __init__(self) -> None:
        self.visits: dict[str, list[bool]] = defaultdict(list)  # account -> had the cookie, in arrival order
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
                account = query.get("account", "")
                if url.path == "/visit":
                    has_cookie = f"session={account}" in self.headers.get("Cookie", "")
                    with site._lock:
                        site.visits[account].append(has_cookie)
                    self._send(f"<p id=state>{'cookie' if has_cookie else 'nocookie'}</p>")
                elif url.path == "/login":
                    # Persistent: it must outlive the browser process, which closes after every task.
                    self._send("<p id=result>ok</p>", cookie=f"session={account}; Path=/; Max-Age=86400")
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


async def test_rows_of_one_account_share_its_browser_directory_and_save_the_login_once(
    tmp_path, valid_profile_values, real_cloak_page, monkeypatch,
):
    executable, _, _ = real_cloak_page
    kernel = next(parent for parent in executable.parents if parent.name.startswith("chromium-"))
    monkeypatch.setattr(browser_resources, "_locate_exit_with_geoip", lambda _url: (None, None))
    monkeypatch.setattr(ledger, "CYCLE_REUSE_SECONDS", 0)  # the second batch may take the same rows again at once
    accounts = [f"acct-{index}" for index in range(ACCOUNTS)]
    await asyncio.to_thread(shutil.copytree, kernel, tmp_path / "data" / "kernels" / kernel.name, symlinks=True)
    app = create_app(Settings(data_dir=str(tmp_path), instance_id="g2", instance_token="g2-token"))
    store = app.state.environment_service.store
    calls = {"prepare": 0, "restore": 0}
    real_prepare, real_restore = store.prepare_instance, store.restore_generation

    def counted_prepare(*args, **kwargs):
        calls["prepare"] += 1
        return real_prepare(*args, **kwargs)

    def counted_restore(*args, **kwargs):
        calls["restore"] += 1
        return real_restore(*args, **kwargs)

    monkeypatch.setattr(store, "prepare_instance", counted_prepare)
    monkeypatch.setattr(store, "restore_generation", counted_restore)
    server = uvicorn.Server(uvicorn.Config(app, lifespan="off", access_log=False, log_level="warning"))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server_task = None
    site = LoginSite()
    snapshots: list[dict] = []
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
            headers={"x-autoflow-token": "g2-token"}, trust_env=False, timeout=60,
        ) as client:

            async def api(method, path, body=None, status=200):
                response = await client.request(method, path, json=body, headers={"Idempotency-Key": str(uuid4())})
                assert response.status_code == status, f"{method} {path}: {response.status_code} {response.text}"
                return response.json()

            project = await api("POST", "/api/v1/projects", {"name": "G2 共用账号", "description": ""}, 201)
            project_id = project["projectId"]
            prefix = f"/api/v1/projects/{project_id}"
            factory = app.state.session_factory
            table, row_field = _empty_table(factory, project_id, "任务")
            account_field = (await api("POST", prefix + f"/tables/{table['tableId']}/fields", {
                "definition": {"key": "account", "name": "账号", "type": "string", "required": False, "validation": {}},
                "sourceColumnPolicy": "localOnly", "expectedTableRevision": 2,
            }))["field"]["ref"]["fieldId"]
            rows: list[tuple[str, str, dict]] = []  # (account, row name, ref)
            for index in range(ACCOUNTS * ROWS_EACH):
                account, name = accounts[index % ACCOUNTS], f"row-{index:03}"
                created = await api("POST", prefix + f"/tables/{table['tableId']}/records", {
                    "datasetGeneration": table["datasetGeneration"],
                    "values": [{"fieldId": row_field["ref"]["fieldId"], "value": name}, {"fieldId": account_field, "value": account}],
                }, 201)
                rows.append((account, name, created["ref"]))
            first_of = {}
            for account, _name, ref in rows:
                first_of.setdefault(account, ref)
            created = await api("POST", prefix + "/identities/from-records", {
                "tableId": table["tableId"], "datasetGeneration": table["datasetGeneration"], "templateProfileId": profile.id,
                "rows": [{"recordKey": ref["recordKey"]["value"], "keyType": ref["recordKey"]["type"], "name": account} for account, ref in first_of.items()],
            })
            identity_of_account = {account: item["identityId"] for account, ref in first_of.items() for item in created["identities"] if item["recordKey"] == ref["recordKey"]["value"]}
            with factory() as session:  # the other rows of an account point at the same identity
                for account, _name, ref in rows:
                    session.get(DataRecordRow, (ref["datasetGeneration"], ref["recordKey"]["type"], ref["recordKey"]["value"])).current_identity_id = identity_of_account[account]
                session.commit()

            account_binding = _binding(project_id, table, account_field, "账号")
            input_spec = {
                "inputId": uid(), "alias": "任务", "tableId": table["tableId"], "datasetGeneration": table["datasetGeneration"],
                "mode": "independent", "required": True, "fieldBindings": [account_binding],
                "filter": {"type": "all", "items": []}, "orderBy": [{"systemField": "recordKey", "direction": "asc"}],
            }
            account = "{PROJECT_INPUTS['" + input_spec["inputId"] + "']['values']['" + account_binding["inputFieldId"] + "']}"
            nodes = [
                flow_node("visit", "open_page", 0, url=f"{site.base_url}/visit?account={account}", timeout=15),
                flow_node("state", "get_element_info", 1, selector="#state", attribute="text", variableName="state", timeout=5),
                flow_node("check", "condition", 2, leftValue="{state}", rightValue="cookie"),
                flow_node("login", "open_page", 3, url=f"{site.base_url}/login?account={account}", timeout=15),
                flow_node("end", "project_end", 4, retainEnvironment=True),
            ]
            edges = [
                {"id": "e1", "source": "visit", "target": "state"},
                {"id": "e2", "source": "state", "target": "check"},
                {"id": "reused", "source": "check", "target": "end", "sourceHandle": "true"},
                {"id": "fresh", "source": "check", "target": "login", "sourceHandle": "false"},
                {"id": "e3", "source": "login", "target": "end"},
            ]
            automation = await api("POST", prefix + "/automations", {
                "name": "G2 同账号共用浏览器", "description": "", "parameterSchema": [],
                "inputPlan": {"inputs": [input_spec]},
                "environmentPolicy": {"source": "inputIdentity", "inputId": input_spec["inputId"], "profileId": profile.id,
                                      "proxyOverride": {"mode": "none"}, "modelProviderId": None},
                "runPolicy": {
                    "maxTasks": ACCOUNTS * ROWS_EACH, "concurrency": CONCURRENCY, "maxLiveInstances": CONCURRENCY,
                    "continueAfterFailure": False, "automaticExecutionTimeoutSeconds": 60, "manualDeadlineSeconds": 120,
                    "claimMode": "cycle", "sessionMode": "perIdentity",
                },
            }, 201)
            workflow_path = f"/api/workflows/{automation['workflowId']}"
            workflow = await api("GET", workflow_path)
            workflow.pop("browserEnvironmentVersion", None)
            await api("PUT", workflow_path, {**workflow, "clientRequestId": str(uuid4()), "expectedRevision": workflow["revision"], "nodes": nodes, "edges": edges})
            automation_path = prefix + f"/automations/{automation['automationId']}"
            validation = await api("GET", automation_path + "/validation")
            assert validation["runnable"] is True, validation

            for _batch in range(2):
                accepted = await api("POST", automation_path + "/batches", {
                    "expectedAutomationRevision": automation["managementRevision"], "parameters": {},
                    "maxTasks": ACCOUNTS * ROWS_EACH, "concurrency": CONCURRENCY, "executionMode": "realWrites",
                }, 202)
                batch_path = prefix + f"/batches/{accepted['operation']['result']['batch']['batchId']}"
                async with asyncio.timeout(900):
                    while (current := (await api("GET", batch_path))["batch"])["status"] not in TERMINAL:
                        await asyncio.sleep(0.5)
                assert current["status"] == "completed", current
                # The batch has ended: the scheduler saves each account's login once and cleans the copies.
                async with asyncio.timeout(180):
                    while True:
                        with factory() as session:
                            held = session.query(ProjectEnvironmentInstanceRow).filter(
                                ProjectEnvironmentInstanceRow.identity_id.is_not(None),
                                ProjectEnvironmentInstanceRow.state.not_in(("cleaned", "retained_unsaved")),
                            ).count()
                        if held == 0:
                            break
                        await asyncio.sleep(0.5)
                with factory() as session:
                    snapshots.append({
                        "instances": [(row.identity_id, row.state, row.instance_use_generation) for row in session.query(ProjectEnvironmentInstanceRow).filter(ProjectEnvironmentInstanceRow.identity_id.is_not(None)).all()],
                        "environments": {row.id: row.content_generation for row in session.query(ProjectEnvironmentRow).all()},
                        "linked": {row.id: row.environment_id for row in session.query(IdentityRow).all()},
                        "visits": {account: list(values) for account, values in site.visits.items()},
                        "calls": dict(calls),
                    })
    finally:
        site.close()
        await app.state.project_run_scheduler.shutdown()
        await app.state.project_workflow_dispatcher.shutdown()
        server.should_exit = True
        if server_task is not None:
            await server_task
        listener.close()

    first, second = snapshots
    identities = set(identity_of_account.values())
    # Batch 1: the first row of an account logs in; its other rows arrive still logged in (same browser directory).
    for account in accounts:
        assert first["visits"][account] == [False] + [True] * (ROWS_EACH - 1), (account, first["visits"][account])
    assert first["calls"] == {"prepare": ACCOUNTS, "restore": 0}, "one work copy per account, never restored from anything"
    # One instance served every row of an account; it counted them in its use generation; the copy is gone.
    assert sorted(item[2] for item in first["instances"]) == [ROWS_EACH] * ACCOUNTS
    assert {item[0] for item in first["instances"]} == identities and {item[1] for item in first["instances"]} == {"cleaned"}
    # The login was saved once per account and now belongs to its identity.
    assert sorted(first["environments"].values()) == [1] * ACCOUNTS
    assert all(first["linked"][identity] in first["environments"] for identity in identities)
    # Batch 2 starts from the saved login: every visit, including each account's first, carries the cookie.
    for account in accounts:
        assert second["visits"][account][ROWS_EACH:] == [True] * ROWS_EACH, (account, second["visits"][account])
    # restore_generation prepares its target through prepare_instance, so each restore adds one of each.
    assert second["calls"] == {"prepare": 2 * ACCOUNTS, "restore": ACCOUNTS}, "batch 2 restores each saved login exactly once"
    assert sorted(second["environments"].values()) == [2] * ACCOUNTS, "one new version per account per batch"
    assert len(second["instances"]) == 2 * ACCOUNTS and {item[2] for item in second["instances"]} == {ROWS_EACH}
