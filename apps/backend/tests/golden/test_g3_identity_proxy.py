"""G3 identity proxies (remediation M4; AC4-01 exit change, AC4-03, AC4-04): real browsers behind local SOCKS5 members.

Twelve accounts run as their identities through a pool of two Shanghai members; a Berlin member joins the pool before
phase C (the exit lookup is a fixture; public echo services are never used). The first binding takes the first usable
member and does not look at the identity's region (a known limit): that is why the pool starts without Berlin. Every request a browser makes reaches the
site through the member's own SOCKS5 server, which stamps the member's name on it, so the site — not the app's
own bookkeeping — says which member each account really used.

  A  first runs      every account binds a member of its own region; the site saw exactly that member.
  B  second batch    the same members again (sticky), whatever the pool's rotation would now pick.
  C  member down     accounts bound to the dead member move to a live one of the SAME region (never Berlin);
                     the stored binding follows.
  D  exit changes    the same member now exits in Berlin: the check refuses Shanghai accounts, naming both regions
                     (the member id being unchanged proves nothing); the failures are infrastructure failures that
                     spend no row budget and pause the batch pointing at the cause. Once the exit is back, resuming
                     runs the rows nobody had claimed yet; the rows the pause had used a task slot for are untouched
                     and run in the next batch.
  E  pool unreachable  every member down: rows fail before any browser starts, the batch pauses naming the proxy,
                     and everything runs after recovery (resume, then the next batch).
Run: AUTOFLOW_TEST_CLOAKBROWSER=<chrome> pytest -m golden tests/golden/test_g3_identity_proxy.py -o faulthandler_timeout=0
"""

from __future__ import annotations

import asyncio
import contextlib
import select
import shutil
import socket
import struct
import threading
from collections import defaultdict
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
import uvicorn
from sqlalchemy import select as sql_select

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.domain.identities.proxy_binding import Member, choose_member
from autoflow.domain.identities.proxy_binding import bind as bind_member
from autoflow.domain.profiles.errors import ProxyUnavailable
from autoflow.domain.profiles.models import ProfileBrowserProxy, ProfileSpec
from autoflow.domain.project_runs import ledger
from autoflow.infrastructure.database.identities import SqlAlchemyIdentities
from autoflow.infrastructure.database.identity_models import IdentityRow
from autoflow.infrastructure.database.project_run_models import (
    ProjectBatchRow,
    ProjectTaskRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_input_groups import _empty_table, uid

from .harness import flow_node

pytestmark = [pytest.mark.golden, pytest.mark.asyncio]

ACCOUNTS = [f"acct-{index}" for index in range(12)]
SHANGHAI, BERLIN = "Asia/Shanghai", "Europe/Berlin"
SITE_HOST = "site.test"  # not loopback: a browser never sends loopback traffic through a proxy
TERMINAL = {"completed", "failed", "interrupted", "stopped"}


class SocksMember:
    """A SOCKS5 server (username/password auth) that forwards to the site and stamps its own name on requests."""

    def __init__(self, name: str, region: str, timezone: str, destination: tuple[str, int]) -> None:
        self.name, self.region, self.timezone, self.exit_ip = name, region, timezone, f"203.0.113.{10 + len(name)}"
        self.up = True
        self._destination = destination
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(64)
        self.port = self.listener.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while True:
            try:
                client, _ = self.listener.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(client,), daemon=True).start()

    def _serve(self, client: socket.socket) -> None:
        upstream = None
        try:
            if not self.up:
                return
            client.settimeout(10)
            count = client.recv(2)[1]
            client.recv(count)
            client.sendall(b"\x05\x02")  # username/password
            client.recv(1)
            client.recv(client.recv(1)[0])
            client.recv(client.recv(1)[0])
            client.sendall(b"\x01\x00")
            _version, _command, _reserved, kind = client.recv(4)
            if kind == 3:
                host = client.recv(client.recv(1)[0]).decode()
            else:
                host = socket.inet_ntoa(client.recv(4))
            port = struct.unpack(">H", client.recv(2))[0]
            target = self._destination if host == SITE_HOST else (host, port)
            upstream = socket.create_connection(target, timeout=10)
            client.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
            stamp = b"\r\nX-Exit-Member: " + self.name.encode() + b"\r\n"
            sockets = [client, upstream]
            while True:
                readable, _, _ = select.select(sockets, [], [], 30)
                if not readable:
                    return
                for source in readable:
                    chunk = source.recv(65536)
                    if not chunk:
                        return
                    if source is client and chunk.startswith((b"GET ", b"POST ")):
                        chunk = chunk.replace(b"\r\n", stamp, 1)
                    (upstream if source is client else client).sendall(chunk)
        except (OSError, IndexError, struct.error):
            return
        finally:
            for item in (client, upstream):
                if item is not None:
                    with suppress(OSError):
                        item.close()


class Site:
    """/visit records which member carried each account's request."""

    def __init__(self) -> None:
        self.visits: dict[str, list[str]] = defaultdict(list)
        self._lock = threading.Lock()
        site = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                return None

            def do_GET(self) -> None:
                url = urlsplit(self.path)
                account = {key: values[0] for key, values in parse_qs(url.query).items()}.get("account", "")
                member = self.headers.get("X-Exit-Member", "direct")
                if url.path == "/visit":
                    with site._lock:
                        site.visits[account].append(member)
                content = b"<p id=state>ok</p>"
                with suppress(BrokenPipeError, ConnectionResetError):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


async def test_identities_keep_their_proxy_member_and_never_run_behind_the_wrong_exit(
    tmp_path, valid_profile_values, real_cloak_page, monkeypatch,
):
    executable, _, _ = real_cloak_page
    kernel = next(parent for parent in executable.parents if parent.name.startswith("chromium-"))
    monkeypatch.setattr(ledger, "CYCLE_REUSE_SECONDS", 0)
    site = Site()
    everyone = {
        "m1": SocksMember("m1", "上海", SHANGHAI, ("127.0.0.1", site.port)),
        "m2": SocksMember("m2", "上海", SHANGHAI, ("127.0.0.1", site.port)),
        "m3": SocksMember("m3", "柏林", BERLIN, ("127.0.0.1", site.port)),
    }
    members = {name: everyone[name] for name in ("m1", "m2")}  # the pool; m3 joins before phase C
    by_port = {member.port: member for member in everyone.values()}
    await asyncio.to_thread(shutil.copytree, kernel, tmp_path / "data" / "kernels" / kernel.name, symlinks=True)
    app = create_app(Settings(data_dir=str(tmp_path), instance_id="g3", instance_token="g3-token"))
    factory = app.state.session_factory
    identities = SqlAlchemyIdentities(factory)
    resources = app.state.project_workflow_resources
    rotation = {"next": 0}

    async def resolve_proxy(profile, request_id, identity_id=None):
        """The real binding rules over the fixture's members (the proxy panel and the vault are not under test)."""
        if identity_id is None:
            return None
        ordered = list(members.values())
        turn = rotation["next"] % len(ordered)
        rotation["next"] += 1
        ordered = ordered[turn:] + ordered[:turn]  # the pool's cursor moves between calls
        for _attempt in range(4):
            binding = identities.proxy_binding(identity_id)
            usable = [Member(member.name, member.region, member.up) for member in ordered]
            choice = choose_member(binding, "pool-1", usable)
            if choice.outcome in {"confirm", "unavailable"} or choice.member_id is None:
                raise ProxyUnavailable(choice.reason or "身份的代理不可用")
            chosen = members[choice.member_id]
            if choice.outcome in {"bind", "replace"}:
                member = next(item for item in usable if item.member_id == chosen.name)
                if not identities.swap_proxy_binding(identity_id, binding, bind_member("pool-1", member, binding)):
                    continue
            return ProfileBrowserProxy(f"socks5://127.0.0.1:{chosen.port}", "user", "pass", chosen.name)
        raise ProxyUnavailable("身份的代理绑定频繁变化，请重试")

    def locate_exit(proxy_url):
        member = by_port[int(proxy_url.rsplit(":", 1)[1])]
        return member.timezone, member.exit_ip

    monkeypatch.setattr(resources, "_resolve_proxy", resolve_proxy)
    monkeypatch.setattr(resources, "_locate_exit", locate_exit)
    server = uvicorn.Server(uvicorn.Config(app, lifespan="off", access_log=False, log_level="warning"))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server_task = None
    seen: dict[str, dict] = {}
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
            headers={"x-autoflow-token": "g3-token"}, trust_env=False, timeout=60,
        ) as client:

            async def api(method, path, body=None, status=200):
                response = await client.request(method, path, json=body, headers={"Idempotency-Key": str(uuid4())})
                assert response.status_code == status, f"{method} {path}: {response.status_code} {response.text}"
                return response.json()

            project = await api("POST", "/api/v1/projects", {"name": "G3 代理", "description": ""}, 201)
            project_id = project["projectId"]
            prefix = f"/api/v1/projects/{project_id}"
            table, key_field = _empty_table(factory, project_id, "账号")
            records = {}
            for account in ACCOUNTS:
                created = await api("POST", prefix + f"/tables/{table['tableId']}/records", {
                    "datasetGeneration": table["datasetGeneration"],
                    "values": [{"fieldId": key_field["ref"]["fieldId"], "value": account}],
                }, 201)
                records[account] = created["ref"]
            batch = await api("POST", prefix + "/identities/from-records", {
                "tableId": table["tableId"], "datasetGeneration": table["datasetGeneration"], "templateProfileId": profile.id,
                "rows": [{"recordKey": ref["recordKey"]["value"], "keyType": ref["recordKey"]["type"], "name": account} for account, ref in records.items()],
            })
            identity_of = {account: item["identityId"] for account in ACCOUNTS for item in batch["identities"] if item["recordKey"] == records[account]["recordKey"]["value"]}
            with factory() as session:
                for account in ACCOUNTS:
                    session.get(IdentityRow, identity_of[account]).region = {"timezone": SHANGHAI}
                session.commit()

            binding_input = {"inputFieldId": uid(), "inputFieldAlias": "账号", "fieldRef": {
                "projectId": project_id, "tableId": table["tableId"], "datasetGeneration": table["datasetGeneration"], "fieldId": key_field["ref"]["fieldId"]}}
            input_spec = {
                "inputId": uid(), "alias": "账号", "tableId": table["tableId"], "datasetGeneration": table["datasetGeneration"],
                "mode": "independent", "required": True, "fieldBindings": [binding_input],
                "filter": {"type": "all", "items": []}, "orderBy": [{"systemField": "recordKey", "direction": "asc"}],
            }
            account = "{PROJECT_INPUTS['" + input_spec["inputId"] + "']['values']['" + binding_input["inputFieldId"] + "']}"
            nodes = [
                flow_node("visit", "open_page", 0, url=f"http://{SITE_HOST}:{site.port}/visit?account={account}", timeout=20),
                flow_node("end", "project_end", 1, retainEnvironment=False),
            ]
            edges = [{"id": "e1", "source": "visit", "target": "end"}]
            automation = await api("POST", prefix + "/automations", {
                "name": "G3 身份代理", "description": "", "parameterSchema": [],
                "inputPlan": {"inputs": [input_spec]},
                "environmentPolicy": {"source": "inputIdentity", "inputId": input_spec["inputId"], "profileId": profile.id,
                                      "proxyOverride": {"mode": "none"}, "modelProviderId": None},
                "runPolicy": {
                    "maxTasks": len(ACCOUNTS), "concurrency": 3, "maxLiveInstances": 3, "continueAfterFailure": True,
                    "automaticExecutionTimeoutSeconds": 60, "manualDeadlineSeconds": 120,
                    "claimMode": "cycle", "failurePolicy": "thresholds", "retryBudget": 2,
                },
            }, 201)
            workflow_path = f"/api/workflows/{automation['workflowId']}"
            workflow = await api("GET", workflow_path)
            workflow.pop("browserEnvironmentVersion", None)
            await api("PUT", workflow_path, {**workflow, "clientRequestId": str(uuid4()), "expectedRevision": workflow["revision"], "nodes": nodes, "edges": edges})
            automation_path = prefix + f"/automations/{automation['automationId']}"

            def stored_members():
                return {name: (identities.proxy_binding(identity_of[name]) or {}).get("memberId") for name in ACCOUNTS}

            def visits_since(marks):
                return {name: site.visits[name][marks.get(name, 0):] for name in ACCOUNTS}

            def marks():
                return {name: len(site.visits[name]) for name in ACCOUNTS}

            async def start_batch():
                accepted = await api("POST", automation_path + "/batches", {
                    "expectedAutomationRevision": automation["managementRevision"], "parameters": {},
                    "maxTasks": len(ACCOUNTS), "concurrency": 3, "executionMode": "realWrites",
                }, 202)
                return prefix + f"/batches/{accepted['operation']['result']['batch']['batchId']}"

            async def settle(batch_path, *, until=("completed", "failed", "paused", "stopped", "interrupted")):
                async with asyncio.timeout(600):
                    while (current := (await api("GET", batch_path))["batch"])["status"] not in until:
                        await asyncio.sleep(0.5)
                return current

            def run_errors(batch_id):
                with factory() as session:
                    rows = session.execute(
                        sql_select(WorkflowRunRow.error).join(ProjectTaskRow, ProjectTaskRow.run_id == WorkflowRunRow.id)
                        .where(ProjectTaskRow.batch_id == batch_id, WorkflowRunRow.status == "failed")
                    ).all()
                return [dict(error or {}) for (error,) in rows]

            def ledger_attempts():
                from autoflow.infrastructure.database.record_ledger_models import (
                    AutomationRecordLedgerRow,
                )

                with factory() as session:
                    return sorted(session.execute(sql_select(AutomationRecordLedgerRow.key_value, AutomationRecordLedgerRow.attempts)).all())

            def task_table(batch_id):
                with factory() as session:
                    rows = session.execute(
                        sql_select(ProjectTaskRow.ordinal, WorkflowRunRow.status, WorkflowRunRow.error).join(WorkflowRunRow, ProjectTaskRow.run_id == WorkflowRunRow.id)
                        .where(ProjectTaskRow.batch_id == batch_id).order_by(ProjectTaskRow.ordinal)
                    ).all()
                return [(ordinal, status, (error or {}).get("code")) for ordinal, status, error in rows]

            def pause_reason(batch_id):
                with factory() as session:
                    return (session.get(ProjectBatchRow, batch_id).selection_outcome or {}).get("pauseReason")

            # ---- A: first runs bind members of the right region -------------------------------------------------
            before = marks()
            path = await start_batch()
            outcome = await settle(path)
            assert outcome["status"] == "completed", (outcome["status"], run_errors(path.rsplit("/", 1)[1]))
            first = visits_since(before)
            bound_a = stored_members()
            assert all(len(first[name]) == 1 for name in ACCOUNTS), first
            assert {name: first[name][0] for name in ACCOUNTS} == bound_a, "the site saw exactly the member each identity is bound to"
            assert set(bound_a.values()) <= {"m1", "m2"}, "an identity from Shanghai is never bound to the Berlin member"
            seen["A"] = {"visits": first, "bound": bound_a}

            # ---- B: the same members again, whatever the pool rotation would now give ---------------------------
            before = marks()
            assert (await settle(await start_batch()))["status"] == "completed"
            assert {name: values[0] for name, values in visits_since(before).items()} == bound_a
            assert stored_members() == bound_a
            seen["B"] = True

            # ---- C: a dead member is replaced by one of the same region ----------------------------------------
            on_m1 = [name for name, member in bound_a.items() if member == "m1"]
            assert on_m1 and len(on_m1) < len(ACCOUNTS), "the scenario needs accounts on both Shanghai members"
            members["m3"] = everyone["m3"]  # a live member in another region is available, and must not be taken
            members["m1"].up = False
            before = marks()
            assert (await settle(await start_batch()))["status"] == "completed"
            third = visits_since(before)
            for name in ACCOUNTS:
                assert third[name] == ["m2"], (name, third[name])  # m1 is gone; m3 is in another region
            assert {name: stored_members()[name] for name in ACCOUNTS} == {name: "m2" for name in ACCOUNTS}, "the binding follows the replacement"
            seen["C"] = third

            # ---- D: the same member now exits in Berlin ---------------------------------------------------------
            members["m2"].timezone, members["m2"].exit_ip = BERLIN, "203.0.113.99"
            resources._exit_cache.clear()
            before = marks()
            attempts_before = ledger_attempts()
            path = await start_batch()
            current = await settle(path)
            batch_id = path.rsplit("/", 1)[1]
            assert current["status"] == "paused", current
            claimed_at_pause = task_table(batch_id)
            refused = run_errors(batch_id)
            assert refused and all(error.get("code") == "IDENTITY_REGION_MISMATCH" for error in refused), refused
            assert all(SHANGHAI in error["message"] and BERLIN in error["message"] for error in refused), "both regions are named"
            assert all(not values for values in visits_since(before).values()), "an account ran behind the wrong exit"
            reason = pause_reason(batch_id)
            assert reason and reason["code"] == "IDENTITY_REGION_MISMATCH" and "环境或代理" in reason["message"], reason
            assert ledger_attempts() == attempts_before, "infrastructure failures spend no row budget"
            members["m2"].timezone, members["m2"].exit_ip = SHANGHAI, "203.0.113.10"
            resources._exit_cache.clear()
            resumed = await api("POST", path + "/resume", {"expectedStatusRevision": current["statusRevision"]}, 202)
            assert resumed["operation"]["status"] == "succeeded"
            await settle(path)
            after_resume = visits_since(before)
            ran = [name for name in ACCOUNTS if after_resume[name]]
            assert len(ran) == len(ACCOUNTS) - len(claimed_at_pause) and all(after_resume[name] == ["m2"] for name in ran),                 "resuming runs the rows nobody had claimed yet, through the same member as before"
            # The rows the pause had already used a task slot for are untouched and run in the next batch.
            assert (await settle(await start_batch()))["status"] == "completed"
            assert all(site.visits[name][before[name]:] and set(site.visits[name][before[name]:]) == {"m2"} for name in ACCOUNTS)
            seen["D"] = len(claimed_at_pause)

            # ---- E: the whole pool is unreachable ---------------------------------------------------------------
            for member in members.values():
                member.up = False
            before = marks()
            attempts_before = ledger_attempts()
            path = await start_batch()
            current = await settle(path)
            batch_id = path.rsplit("/", 1)[1]
            assert current["status"] == "paused", current
            errors = run_errors(batch_id)
            assert errors and all(error.get("code") == "PROXY_UNAVAILABLE" for error in errors), errors
            assert all(not values for values in visits_since(before).values()), "no browser started without a proxy"
            assert pause_reason(batch_id)["code"] == "PROXY_UNAVAILABLE"
            assert ledger_attempts() == attempts_before
            for member in members.values():
                member.up = True
            resumed = await api("POST", path + "/resume", {"expectedStatusRevision": current["statusRevision"]}, 202)
            assert resumed["operation"]["status"] == "succeeded"
            await settle(path)
            assert (await settle(await start_batch()))["status"] == "completed"
            assert all(site.visits[name][before[name]:] for name in ACCOUNTS), "every account ran once the pool was back"
            seen["E"] = True
    finally:
        site.close()
        await app.state.project_run_scheduler.shutdown()
        await app.state.project_workflow_dispatcher.shutdown()
        server.should_exit = True
        if server_task is not None:
            await server_task
        listener.close()
        for member in everyone.values():
            with contextlib.suppress(OSError):
                member.listener.close()
    assert set(seen) == {"A", "B", "C", "D", "E"}
