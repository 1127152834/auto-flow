"""Merge PM4 and Studio histories while keeping their run stores independent."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_merge_project_runtime"
down_revision = ("0012_workflow_document_requests", "pm06_project_capability_reads")
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    # PM4's durable core and the current Studio both inherited the old workflow
    # table names. Preserve the PM4 history under a project-owned namespace,
    # then restore the Studio schema and its legacy payloads losslessly.
    for name, table in (
        ("ix_workflow_artifacts_purpose", "workflow_run_artifacts"),
        ("ix_workflow_artifacts_execution", "workflow_run_artifacts"),
        ("ix_workflow_artifacts_node", "workflow_run_artifacts"),
        ("ix_workflow_runs_prepared_status", "workflow_runs"),
        (
            "ix_workflow_prepared_contents_workflow_created",
            "workflow_prepared_contents",
        ),
    ):
        op.drop_index(name, table_name=table)

    for source, target in (
        ("workflow_debug_commands", "project_workflow_debug_commands"),
        ("workflow_run_artifacts", "project_workflow_run_artifacts"),
        ("workflow_run_events", "project_workflow_run_events"),
        ("workflow_runs", "project_workflow_runs"),
        ("workflow_prepared_contents", "project_workflow_prepared_contents"),
    ):
        op.rename_table(source, target)

    op.create_index(
        "ix_project_workflow_prepared_contents_workflow_created",
        "project_workflow_prepared_contents",
        ["workflow_id", "created_at"],
    )
    op.create_index(
        "ix_project_workflow_runs_prepared_status",
        "project_workflow_runs",
        ["prepared_content_id", "status"],
    )
    op.create_index(
        "ix_project_workflow_artifacts_node",
        "project_workflow_run_artifacts",
        ["run_id", "node_id", "ordinal"],
    )
    op.create_index(
        "ix_project_workflow_artifacts_execution",
        "project_workflow_run_artifacts",
        ["run_id", "execution_id", "ordinal"],
    )
    op.create_index(
        "ix_project_workflow_artifacts_purpose",
        "project_workflow_run_artifacts",
        ["run_id", "purpose", "ordinal"],
    )

    _create_studio_tables()

    # 0011 stored the exact old payload and event bodies in the durable core.
    # It runs in the same Alembic upgrade as this merge, so no PM4-owned rows can
    # exist between the two revisions on an application-managed database.
    connection.execute(
        sa.text(
            """INSERT INTO workflow_runs
               (id, workflow_id, request_hash, started_at, active_slot, payload)
               SELECT r.id, p.workflow_id, r.request_digest,
                      CAST(r.created_at AS TEXT),
                      CASE
                        WHEN json_extract(p.provenance, '$.legacyPayload.cleanupState') = 'pending' THEN 2
                        WHEN lower(coalesce(
                          json_extract(p.provenance, '$.legacyPayload.status'),
                          json_extract(p.provenance, '$.legacyPayload.state'),
                          ''
                        )) IN ('starting','running','paused') THEN 1
                        ELSE NULL
                      END,
                      json_extract(p.provenance, '$.legacyPayload')
               FROM project_workflow_runs AS r
               JOIN project_workflow_prepared_contents AS p
                 ON p.id = r.prepared_content_id
               WHERE json_extract(p.provenance, '$.legacy') = 1"""
        )
    )
    connection.execute(
        sa.text(
            """INSERT INTO workflow_run_events (run_id, seq, payload)
               SELECT e.run_id, e.sequence, e.payload
               FROM project_workflow_run_events AS e
               JOIN workflow_runs AS r ON r.id = e.run_id"""
        )
    )
    connection.execute(
        sa.text(
            """INSERT INTO workflow_run_artifacts
               (run_id, id, ordinal, node_id, execution_id, payload, purpose, event_seq)
               SELECT a.run_id, a.id, a.ordinal, a.node_id, a.execution_id,
                      a.payload, a.purpose, a.event_seq
               FROM project_workflow_run_artifacts AS a
               JOIN workflow_runs AS r ON r.id = a.run_id"""
        )
    )
    connection.execute(
        sa.text(
            """INSERT INTO workflow_debug_commands
               (run_id, id, request_hash, payload)
               SELECT c.run_id, c.id, c.request_hash, c.payload
               FROM project_workflow_debug_commands AS c
               JOIN workflow_runs AS r ON r.id = c.run_id"""
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT 1 FROM workflow_runs LIMIT 1")).first():
        raise RuntimeError(
            "WORKFLOW_RUNTIME_DOWNGRADE_UNSAFE: Studio run evidence exists; "
            "restore a pre-integration backup instead"
        )

    op.drop_table("workflow_debug_commands")
    op.drop_index("ix_workflow_artifacts_purpose", table_name="workflow_run_artifacts")
    op.drop_index("ix_workflow_artifacts_execution", table_name="workflow_run_artifacts")
    op.drop_index("ix_workflow_artifacts_node", table_name="workflow_run_artifacts")
    op.drop_table("workflow_run_artifacts")
    op.drop_table("workflow_run_events")
    op.drop_index("ix_workflow_runs_workflow_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")

    for name, table in (
        (
            "ix_project_workflow_artifacts_purpose",
            "project_workflow_run_artifacts",
        ),
        (
            "ix_project_workflow_artifacts_execution",
            "project_workflow_run_artifacts",
        ),
        ("ix_project_workflow_artifacts_node", "project_workflow_run_artifacts"),
        ("ix_project_workflow_runs_prepared_status", "project_workflow_runs"),
        (
            "ix_project_workflow_prepared_contents_workflow_created",
            "project_workflow_prepared_contents",
        ),
    ):
        op.drop_index(name, table_name=table)

    for source, target in (
        ("project_workflow_debug_commands", "workflow_debug_commands"),
        ("project_workflow_run_artifacts", "workflow_run_artifacts"),
        ("project_workflow_run_events", "workflow_run_events"),
        ("project_workflow_runs", "workflow_runs"),
        ("project_workflow_prepared_contents", "workflow_prepared_contents"),
    ):
        op.rename_table(source, target)

    op.create_index(
        "ix_workflow_prepared_contents_workflow_created",
        "workflow_prepared_contents",
        ["workflow_id", "created_at"],
    )
    op.create_index(
        "ix_workflow_runs_prepared_status",
        "workflow_runs",
        ["prepared_content_id", "status"],
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


def _create_studio_tables() -> None:
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
        sa.UniqueConstraint("run_id", "ordinal", name="uq_workflow_artifact_ordinal"),
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
