"""Replace retired Studio run storage with the durable core runtime contract."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision = "0011_workflow_runtime_contracts"
down_revision = "0010_workflow_document_commands"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    migration_time = datetime.now(UTC).isoformat()
    legacy_runs = list(
        connection.execute(
            sa.text(
                """SELECT r.id, r.workflow_id, r.request_hash, r.started_at,
                          r.active_slot, r.payload, d.id AS document_id,
                          d.document AS workflow_document
                   FROM workflow_runs AS r
                   LEFT JOIN workflow_documents AS d ON d.id = r.workflow_id
                   ORDER BY r.id"""
            )
        ).mappings()
    )
    legacy_events = list(
        connection.execute(
            sa.text(
                "SELECT run_id, seq, payload FROM workflow_run_events "
                "ORDER BY run_id, seq"
            )
        ).mappings()
    )

    _drop_legacy_indexes()
    op.rename_table("workflow_debug_commands", "workflow_debug_commands_legacy")
    op.rename_table("workflow_run_artifacts", "workflow_run_artifacts_legacy")
    op.rename_table("workflow_run_events", "workflow_run_events_legacy")
    op.rename_table("workflow_runs", "workflow_runs_legacy")

    _create_runtime_tables()

    max_sequence: dict[str, int] = {}
    for row in legacy_events:
        run_id = str(row["run_id"])
        max_sequence[run_id] = max(max_sequence.get(run_id, 0), int(row["seq"]))

    known_workflows = {
        str(value)
        for value in connection.execute(
            sa.text("SELECT id FROM workflow_documents")
        ).scalars()
    }
    for row in legacy_runs:
        run_id = str(row["id"])
        workflow_id = str(row["workflow_id"])
        payload = _json_object(row["payload"])
        stored_document = _json_object(row["workflow_document"])
        snapshot = _json_value(payload.get("document"))
        has_snapshot = isinstance(snapshot, dict)
        document = snapshot if has_snapshot else stored_document
        started_at = str(payload.get("startedAt") or row["started_at"])
        if workflow_id not in known_workflows:
            placeholder = {
                "legacy": True,
                "missingSourceDocument": True,
                "workflowId": workflow_id,
            }
            connection.execute(
                sa.text(
                    """INSERT INTO workflow_documents
                       (id, name, document, layout, revision, created_at, updated_at)
                       VALUES (:id, :name, :document, '{}', 1, :created_at, :updated_at)"""
                ),
                {
                    "id": workflow_id,
                    "name": f"Legacy workflow {workflow_id}",
                    "document": _json_text(placeholder),
                    "created_at": started_at,
                    "updated_at": started_at,
                },
            )
            known_workflows.add(workflow_id)
        prepared_content_id = _stable_id(f"prepared-content:{run_id}")
        adapter_version = "legacy-readonly/v1"
        node_order = _json_list(payload.get("nodeOrder"))
        execution_plan = {
            "kind": "legacyFrozenPlan",
            "legacyRunId": run_id,
            "orderedNodeIds": node_order,
            "nodes": _legacy_execution_nodes(document, node_order),
            "replayable": False,
        }
        provenance = {
            "legacy": True,
            "legacyRunId": run_id,
            "adapterVersion": adapter_version,
            "source": "workflow_runs.v1",
            "replayable": False,
            "originalState": payload.get("state", payload.get("status")),
            "originalFinishedAt": payload.get("finishedAt"),
            "legacyPayload": payload,
            "documentSource": "runSnapshot" if has_snapshot else "currentDocumentFallback",
            "startupFacts": {
                "name": payload.get("name"),
                "layout": _json_object(payload.get("layout")),
                "profileId": payload.get("profileId"),
                "profileName": payload.get("profileName"),
                "profileSnapshot": _json_object(payload.get("profileSnapshot")),
                "warnings": _json_list(payload.get("warnings")),
            },
        }
        connection.execute(
            sa.text(
                """INSERT INTO workflow_prepared_contents
                   (id, prepare_operation_id, request_digest, workflow_id,
                    source_revision, checksum, document, execution_plan,
                    adapter_version, capability_requirements, provenance, created_at)
                   VALUES
                   (:id, :prepare_operation_id, :request_digest, :workflow_id,
                    NULL, :checksum, :document, :execution_plan,
                    :adapter_version, :capability_requirements, :provenance, :created_at)"""
            ),
            {
                "id": prepared_content_id,
                "prepare_operation_id": _stable_id(f"prepare-operation:{run_id}"),
                "request_digest": str(row["request_hash"]),
                "workflow_id": workflow_id,
                "checksum": _digest(document),
                "document": _json_text(document),
                "execution_plan": _json_text(execution_plan),
                "adapter_version": adapter_version,
                "capability_requirements": "[]",
                "provenance": _json_text(provenance),
                "created_at": started_at,
            },
        )

        status = _legacy_status(payload)
        terminal = status in {
            "succeeded",
            "failed",
            "cancelled",
            "timed_out",
            "interrupted",
        }
        error = payload.get("error")
        original_state = str(payload.get("status", payload.get("state", ""))).lower()
        if status == "interrupted" and original_state != "interrupted":
            error = {
                "code": "LEGACY_RUN_INTERRUPTED",
                "message": "旧运行的进程归属无法证明，迁移后不会自动重放",
                "legacyError": payload.get("error"),
            }
        original_finished_at = payload.get("finishedAt")
        completed_at = original_finished_at if terminal else None
        inferred_completion = terminal and not original_finished_at
        if inferred_completion:
            completed_at = migration_time
        provenance["completion"] = {
            "inferred": inferred_completion,
            "originalFinishedAt": original_finished_at,
            "recordedAt": completed_at,
        }
        connection.execute(
            sa.text(
                "UPDATE workflow_prepared_contents SET provenance=:provenance "
                "WHERE id=:id"
            ),
            {"id": prepared_content_id, "provenance": _json_text(provenance)},
        )
        connection.execute(
            sa.text(
                """INSERT INTO workflow_runs
                   (id, run_request_id, request_digest, prepared_content_id,
                    parameters, input_snapshot_ref, resource_request,
                    capability_bindings, status, status_revision,
                    execution_generation, last_sequence, created_at, updated_at,
                    started_at, completed_at, error)
                   VALUES
                   (:id, :run_request_id, :request_digest, :prepared_content_id,
                    :parameters, :input_snapshot_ref, :resource_request,
                    :capability_bindings, :status, 1, 0, :last_sequence,
                    :created_at, :updated_at, :started_at, :completed_at, :error)"""
            ),
            {
                "id": run_id,
                "run_request_id": _stable_id(f"run-request:{run_id}"),
                "request_digest": str(row["request_hash"]),
                "prepared_content_id": prepared_content_id,
                "parameters": _json_text(payload.get("parameters", {})),
                "input_snapshot_ref": _nullable_json_text(
                    payload.get("inputSnapshotRef")
                ),
                "resource_request": _json_text(
                    payload.get("resourceRequest")
                    or {
                        "profileId": payload.get("profileId"),
                        "profileName": payload.get("profileName"),
                        "profileSnapshot": _json_object(
                            payload.get("profileSnapshot")
                        ),
                    }
                ),
                "capability_bindings": _json_text(
                    payload.get("capabilityBindings", [])
                ),
                "status": status,
                "last_sequence": max(
                    max_sequence.get(run_id, 0),
                    int(payload.get("latestSeq", 0)),
                ),
                "created_at": started_at,
                "updated_at": started_at,
                "started_at": started_at,
                "completed_at": completed_at,
                "error": _nullable_json_text(error),
            },
        )

    for row in legacy_events:
        payload = _json_object(row["payload"])
        run_id = str(row["run_id"])
        sequence = int(row["seq"])
        connection.execute(
            sa.text(
                """INSERT INTO workflow_run_events
                   (run_id, sequence, event_id, execution_generation, kind,
                    node_id, node_visit_id, attempt, occurred_at, payload)
                   VALUES
                   (:run_id, :sequence, :event_id, 0, :kind,
                    :node_id, :node_visit_id, :attempt, :occurred_at, :payload)"""
            ),
            {
                "run_id": run_id,
                "sequence": sequence,
                "event_id": _stable_id(f"run-event:{run_id}:{sequence}"),
                "kind": _legacy_event_kind(payload),
                "node_id": (
                    str(payload["nodeId"])
                    if payload.get("nodeId") is not None
                    else None
                ),
                "node_visit_id": _legacy_node_visit_id(payload, run_id, sequence),
                "attempt": _legacy_attempt(payload),
                "occurred_at": _legacy_event_time(payload, legacy_runs, run_id),
                "payload": _json_text(payload),
            },
        )

    connection.execute(
        sa.text(
            """INSERT INTO workflow_run_artifacts
               (run_id, id, ordinal, node_id, execution_id, payload, purpose, event_seq)
               SELECT run_id, id, ordinal, node_id, execution_id, payload, purpose, event_seq
               FROM workflow_run_artifacts_legacy"""
        )
    )
    connection.execute(
        sa.text(
            """INSERT INTO workflow_debug_commands
               (run_id, id, request_hash, payload)
               SELECT run_id, id, request_hash, payload
               FROM workflow_debug_commands_legacy"""
        )
    )

    op.drop_table("workflow_debug_commands_legacy")
    op.drop_table("workflow_run_artifacts_legacy")
    op.drop_table("workflow_run_events_legacy")
    op.drop_table("workflow_runs_legacy")


def downgrade() -> None:
    connection = op.get_bind()
    # The old schema cannot represent immutable snapshots, operation identities or
    # generation fencing. Refuse before any DDL instead of discarding evidence.
    if connection.execute(
        sa.text("SELECT 1 FROM workflow_prepared_contents LIMIT 1")
    ).first() is not None:
        raise RuntimeError(
            "WORKFLOW_RUNTIME_DOWNGRADE_UNSAFE: persisted runtime evidence "
            "cannot be represented by the retired schema; restore a pre-upgrade "
            "backup to use that version"
        )
    _drop_runtime_indexes()
    op.drop_table("workflow_debug_commands")
    op.drop_table("workflow_run_artifacts")
    op.drop_table("workflow_run_events")
    op.drop_table("workflow_runs")
    op.drop_table("workflow_prepared_contents")
    _create_legacy_tables()


def _create_runtime_tables() -> None:
    op.create_table(
        "workflow_prepared_contents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("prepare_operation_id", sa.String(36), nullable=False, unique=True),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column(
            "workflow_id",
            sa.String(36),
            sa.ForeignKey("workflow_documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_revision", sa.Integer()),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("execution_plan", sa.JSON(), nullable=False),
        sa.Column("adapter_version", sa.String(80), nullable=False),
        sa.Column("capability_requirements", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_revision IS NULL OR source_revision >= 1",
            name="ck_workflow_prepared_source_revision",
        ),
    )
    op.create_index(
        "ix_workflow_prepared_contents_workflow_created",
        "workflow_prepared_contents",
        ["workflow_id", "created_at"],
    )
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column(
            "prepared_content_id",
            sa.String(36),
            sa.ForeignKey("workflow_prepared_contents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("input_snapshot_ref", sa.JSON()),
        sa.Column("resource_request", sa.JSON(), nullable=False),
        sa.Column("capability_bindings", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("status_revision", sa.Integer(), nullable=False),
        sa.Column("execution_generation", sa.Integer(), nullable=False),
        sa.Column("last_sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.JSON()),
        sa.CheckConstraint(
            "status IN ('queued','running','waiting_manual','resume_queued',"
            "'finishing','stopping','reconciling','succeeded','failed',"
            "'cancelled','timed_out','interrupted')",
            name="ck_workflow_runs_status",
        ),
        sa.CheckConstraint(
            "status_revision >= 1 AND execution_generation >= 0 "
            "AND last_sequence >= 0",
            name="ck_workflow_runs_revisions",
        ),
    )
    op.create_index(
        "ix_workflow_runs_prepared_status",
        "workflow_runs",
        ["prepared_content_id", "status"],
    )
    op.create_table(
        "workflow_run_events",
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("sequence", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("execution_generation", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("node_id", sa.String(120)),
        sa.Column("node_visit_id", sa.String(120)),
        sa.Column("attempt", sa.Integer()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("run_id", "event_id", name="uq_workflow_run_event_id"),
        sa.CheckConstraint("sequence >= 1", name="ck_workflow_run_event_sequence"),
        sa.CheckConstraint(
            "execution_generation >= 0",
            name="ck_workflow_run_event_generation",
        ),
        sa.CheckConstraint(
            "attempt IS NULL OR attempt >= 1",
            name="ck_workflow_run_event_attempt",
        ),
    )
    _create_runtime_dependents()


def _create_runtime_dependents() -> None:
    op.create_table(
        "workflow_run_artifacts",
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.String(120), nullable=False),
        sa.Column("execution_id", sa.String(120)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("event_seq", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "run_id", "ordinal", name="uq_workflow_artifact_ordinal"
        ),
    )
    op.create_index(
        "ix_workflow_artifacts_node",
        "workflow_run_artifacts",
        ["run_id", "node_id", "ordinal"],
    )
    op.create_index(
        "ix_workflow_artifacts_execution",
        "workflow_run_artifacts",
        ["run_id", "execution_id", "ordinal"],
    )
    op.create_index(
        "ix_workflow_artifacts_purpose",
        "workflow_run_artifacts",
        ["run_id", "purpose", "ordinal"],
    )
    op.create_table(
        "workflow_debug_commands",
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def _create_legacy_tables() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("started_at", sa.String(40), nullable=False),
        sa.Column("active_slot", sa.Integer(), unique=True),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_workflow_runs_workflow_id", "workflow_runs", ["workflow_id"])
    op.create_table(
        "workflow_run_events",
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("seq", sa.Integer(), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    _create_runtime_dependents()


def _drop_legacy_indexes() -> None:
    op.drop_index("ix_workflow_artifacts_purpose", table_name="workflow_run_artifacts")
    op.drop_index("ix_workflow_artifacts_execution", table_name="workflow_run_artifacts")
    op.drop_index("ix_workflow_artifacts_node", table_name="workflow_run_artifacts")
    op.drop_index("ix_workflow_runs_workflow_id", table_name="workflow_runs")


def _drop_runtime_indexes() -> None:
    op.drop_index("ix_workflow_artifacts_purpose", table_name="workflow_run_artifacts")
    op.drop_index("ix_workflow_artifacts_execution", table_name="workflow_run_artifacts")
    op.drop_index("ix_workflow_artifacts_node", table_name="workflow_run_artifacts")
    op.drop_index("ix_workflow_runs_prepared_status", table_name="workflow_runs")
    op.drop_index(
        "ix_workflow_prepared_contents_workflow_created",
        table_name="workflow_prepared_contents",
    )


def _legacy_status(payload: dict[str, Any]) -> str:
    value = str(payload.get("status", payload.get("state", ""))).lower()
    aliases = {"completed": "succeeded", "success": "succeeded", "canceled": "cancelled"}
    mapped = aliases.get(value, value)
    if mapped in {"succeeded", "failed", "cancelled", "timed_out", "interrupted"}:
        return mapped
    return "interrupted"


def _legacy_event_kind(payload: dict[str, Any]) -> str:
    value = str(payload.get("kind", payload.get("type", "runStatus"))).lower()
    if "log" in value:
        return "log"
    if "output" in value or "result" in value:
        return "output"
    if "checkpoint" in value or "pause" in value:
        return "checkpoint"
    if "node" in value:
        return "nodeAttempt"
    return "runStatus"


def _legacy_node_visit_id(
    payload: dict[str, Any], run_id: str, sequence: int
) -> str | None:
    value = payload.get("nodeVisitId")
    if value is not None:
        return str(value)
    node_id = payload.get("nodeId")
    return f"legacy:{run_id}:{sequence}:{node_id}" if node_id is not None else None


def _legacy_attempt(payload: dict[str, Any]) -> int | None:
    value = payload.get("attempt")
    return int(value) if isinstance(value, int) else None


def _legacy_execution_nodes(
    document: dict[str, Any], node_order: list[Any]
) -> list[dict[str, Any]]:
    nodes = document.get("nodes")
    if not isinstance(nodes, list):
        content = document.get("content")
        nodes = content.get("nodes") if isinstance(content, dict) else []
    if not isinstance(nodes, list):
        nodes = []
    by_id = {
        str(node.get("id")): node
        for node in nodes
        if isinstance(node, dict) and node.get("id") is not None
    }
    return [
        {"nodeId": str(node_id), "snapshot": by_id.get(str(node_id), {})}
        for node_id in node_order
    ]


def _legacy_event_time(
    payload: dict[str, Any], legacy_runs: list[Any], run_id: str
) -> str:
    value = payload.get("occurredAt", payload.get("timestamp"))
    if isinstance(value, str) and value:
        return value
    for run in legacy_runs:
        if str(run["id"]) == run_id:
            return str(run["started_at"])
    return datetime.now(UTC).isoformat()


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _json_object(value: Any) -> dict[str, Any]:
    parsed = _json_value(value)
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: Any) -> list[Any]:
    parsed = _json_value(value)
    return parsed if isinstance(parsed, list) else []


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _nullable_json_text(value: Any) -> str | None:
    return None if value is None else _json_text(value)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json_text(value).encode()).hexdigest()


def _stable_id(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"autoflow:{value}"))
