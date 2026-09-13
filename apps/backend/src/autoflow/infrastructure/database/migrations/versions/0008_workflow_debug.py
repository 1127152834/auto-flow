"""Debug command identities and diagnostic artifacts without altering old records."""
import sqlalchemy as sa
from alembic import op

revision = '0008_workflow_debug'
down_revision = '0007_workflow_artifacts'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('workflow_run_artifacts', sa.Column('purpose', sa.String(20), nullable=False, server_default='result'))
    op.add_column('workflow_run_artifacts', sa.Column('event_seq', sa.Integer(), nullable=False, server_default='0'))
    # Preserve cutoff semantics for existing results using their original event.
    op.execute("""
        UPDATE workflow_run_artifacts SET event_seq = origin.event_seq
        FROM (
          SELECT run_id, json_extract(payload, '$.artifactId') AS artifact_id, MIN(seq) AS event_seq
          FROM workflow_run_events WHERE json_type(payload, '$.artifactId') = 'text'
          GROUP BY run_id, artifact_id
        ) AS origin
        WHERE workflow_run_artifacts.run_id = origin.run_id
          AND workflow_run_artifacts.id = origin.artifact_id
    """)
    op.create_index('ix_workflow_artifacts_purpose', 'workflow_run_artifacts', ['run_id', 'purpose', 'ordinal'])
    op.create_table('workflow_debug_commands',
        sa.Column('run_id', sa.String(36), sa.ForeignKey('workflow_runs.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('id', sa.String(120), primary_key=True),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False))


def downgrade():
    op.drop_table('workflow_debug_commands')
    op.drop_index('ix_workflow_artifacts_purpose', 'workflow_run_artifacts')
    op.drop_column('workflow_run_artifacts', 'event_seq')
    op.drop_column('workflow_run_artifacts', 'purpose')
