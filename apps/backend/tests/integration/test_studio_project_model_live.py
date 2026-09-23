"""Opt-in real provider/OS credential/worker acceptance; main model DB is read-only."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import quote, urlsplit

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from autoflow.application.models.service import ModelService
from autoflow.bootstrap.workflows import build_workflow_services
from autoflow.domain.credentials import CredentialStoreUnavailableError
from autoflow.domain.models.errors import ModelError
from autoflow.domain.workflows.runs import WorkflowRunError
from autoflow.infrastructure.credentials.system import SystemCredentialStore
from autoflow.infrastructure.database.model_providers import (
    model_repository_transaction,
)
from autoflow.infrastructure.database.models import ProjectRow
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.filesystem.profile_data import FilesystemProfileUsageGuard
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager
from autoflow.providers.model.http import HttpModelProvider
from tests.unit.workflows.test_run_coordinator import FakeProfiles, _none, _profile

pytestmark = pytest.mark.skipif(
    os.environ.get("AUTOFLOW_LIVE_MODEL_TEST") != "1",
    reason="真实模型计费验收仅由 AUTOFLOW_LIVE_MODEL_TEST=1 显式启用",
)

MAIN_DATABASE = (
    Path.home() / "Library/Application Support/@autoflow/desktop/data/autoflow.sqlite3"
)
EVIDENCE = (
    Path(__file__).resolve().parents[4]
    / "docs/migration/studio-backend-migration/evidence/project-integration/model-defaults-live-2026-09-23"
)


def _write_evidence(value: dict[str, Any]) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "real-model.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_live_project_default_model_in_real_worker(tmp_path: Path) -> None:
    evidence: dict[str, Any] = {
        "checkedAt": datetime.now(UTC).isoformat(),
        "status": "pending",
        "boundary": "真实系统凭据、真实外部模型、真实 worker；不含 Electron UI 验收",
        "mainDatabaseAccess": "SQLite URI mode=ro; PRAGMA query_only=ON on every connection",
        "projectRunStorage": "independent temporary workspace",
        "browserUsed": False,
        "externalCallsPlanned": 1,
    }
    if not MAIN_DATABASE.is_file():
        evidence.update(status="blocked", reasonCode="MAIN_MODEL_DATABASE_MISSING")
        _write_evidence(evidence)
        pytest.skip("主应用模型数据库不存在")

    connection_count = 0

    def connect_readonly() -> sqlite3.Connection:
        nonlocal connection_count
        connection = sqlite3.connect(
            "file:" + quote(str(MAIN_DATABASE)) + "?mode=ro",
            uri=True,
            check_same_thread=False,
        )
        connection.execute("PRAGMA query_only=ON")
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        connection_count += 1
        return connection

    main_engine = create_engine(
        "sqlite://", creator=connect_readonly, poolclass=NullPool
    )
    model_sessions = sessionmaker(bind=main_engine, expire_on_commit=False)
    sessions = None
    services = None
    run_id = "live-project-default-model"
    started = perf_counter()
    try:
        model_service = ModelService(
            partial(model_repository_transaction, model_sessions),
            SystemCredentialStore(),
            HttpModelProvider(),
        )
        options = model_service.list_options()
        if not options:
            evidence.update(status="blocked", reasonCode="NO_ENABLED_MAIN_MODEL")
            pytest.skip("主应用尚无启用模型")
        provider_id = options[0].provider_id
        model_id = model_service.default_model_id(provider_id)
        provider = model_service.get_provider(provider_id)
        evidence.update(
            providerId=provider_id,
            modelId=model_id,
            providerKind=provider.provider_kind,
            providerHostname=urlsplit(provider.base_url or "").hostname,
        )
        workspace_database = tmp_path / "workspace.sqlite3"
        migrate_database(workspace_database)
        sessions = create_session_factory(workspace_database)
        now = datetime.now(UTC)
        with sessions() as session:
            session.add(
                ProjectRow(
                    id="live-model-project",
                    name="真实默认模型验收",
                    name_key="真实默认模型验收",
                    description="",
                    search_text="",
                    default_resources={"modelProviderId": provider_id},
                    management_revision=1,
                    lifecycle_state="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        services = build_workflow_services(
            sessions,
            models=model_service,
            # A pure AI node does not acquire or launch a browser. This fixture
            # supplies only the required launch-profile metadata, not a model/worker.
            profiles=FakeProfiles(_profile()),
            installed_kernels=list,
            resolve_proxy=lambda _profile, _run: _none(),
            read_license=lambda: None,
            profile_guard=FilesystemProfileUsageGuard(tmp_path / "profiles"),
            kernels_root=tmp_path / "kernels",
            temp_root=tmp_path / "workers",
            artifact_root=tmp_path / "artifacts",
        )
        assert isinstance(services.workers, WorkflowWorkerManager)
        document = {
            "id": "live-model-flow",
            "name": "真实默认模型验收",
            "projectId": "live-model-project",
            "nodes": [
                {
                    "id": "ask",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "ai_chat",
                        "config": {
                            "modelId": "",
                            "userPrompt": "请只回复：项目默认模型验收成功",
                            "maxTokens": 400,
                            "temperature": 0,
                            "timeoutSeconds": 90,
                            "variableName": "answer",
                        },
                    },
                }
            ],
            "edges": [],
            "variables": [],
        }
        saved = services.documents.create(document, client_request_id="live-model-save")
        async with asyncio.timeout(120):
            await services.commands.start(
                "live-model-flow",
                {
                    "runId": run_id,
                    "documentId": "live-model-flow",
                    "profileId": "profile-1",
                    "projectId": "live-model-project",
                    "document": document,
                },
            )
            while services.workers.busy():
                await asyncio.sleep(0.05)
        run = services.runs.get(run_id)
        evidence.update(runStatus=run.status, cleanupState=run.cleanup_state)
        if run.status != "completed":
            evidence.update(
                status="blocked",
                reasonCode="REAL_MODEL_RUN_NOT_COMPLETED",
                failure=run.error,
            )
            pytest.fail("真实模型运行未成功；已保存无凭据的失败证据")
        events = services.runs.events(run_id)
        completed = [
            event for event in events if event.type == "execution:node-succeeded"
        ]
        assert len(completed) == 1
        result = completed[0].payload["result"]["data"]
        assert result["modelId"] == model_id
        assert "项目默认模型验收成功" in result["response"]
        assert run.cleanup_state == "completed"
        assert services.documents.get(saved.id) == saved
        assert run.document_snapshot["nodes"][0]["data"]["config"]["modelId"] == ""
        public = json.dumps(
            {
                "document": run.document_snapshot,
                "profile": run.profile_snapshot,
                "modules": run.custom_module_snapshots,
                "events": [event.payload for event in events],
            },
            ensure_ascii=False,
        )
        for private_field in (
            "modelBindings",
            "secret_ref",
            '"secret"',
            '"authorization"',
        ):
            assert private_field not in public
        evidence.update(
            status="passed",
            nodeId="ask",
            executionId=completed[0].execution_id,
            response=result["response"],
            model=result["model"],
            usage=result["usage"],
            eventCount=len(events),
            savedDocumentUnchanged=True,
            rawSnapshotUnchanged=True,
        )
    except (CredentialStoreUnavailableError, ModelError, WorkflowRunError) as error:
        evidence.update(
            status="blocked", reasonCode=getattr(error, "code", type(error).__name__)
        )
        pytest.fail("真实模型验收被资源或凭据边界阻塞；错误码已记入证据", pytrace=False)
    except TimeoutError:
        evidence.update(status="blocked", reasonCode="LIVE_MODEL_DEADLINE_EXCEEDED")
        pytest.fail("真实模型验收超出120秒上限", pytrace=False)
    except AssertionError:
        evidence.update(status="failed", reasonCode="LIVE_MODEL_ASSERTION_FAILED")
        raise
    finally:
        try:
            if services is not None:
                await asyncio.wait_for(services.shutdown(), timeout=30)
                assert services.workers is not None
                evidence["remainingWorkerPids"] = services.workers.active_processes()
                evidence["busyAfterCleanup"] = services.workers.busy()
                evidence["serviceBlockersAfterCleanup"] = services.blockers()
                assert not services.workers.busy()
                assert services.workers.active_processes() == []
                assert services.blockers() == []
        except BaseException:
            evidence.update(status="failed", reasonCode="LIVE_MODEL_CLEANUP_FAILED")
            raise
        finally:
            evidence["elapsedSeconds"] = round(perf_counter() - started, 3)
            evidence["readOnlyModelConnections"] = connection_count
            _write_evidence(evidence)
            if sessions is not None:
                sessions.dispose()
            main_engine.dispose()
