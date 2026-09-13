"""Index per-execution artifacts without rewriting the run's whole result list."""
import sqlalchemy as sa
from alembic import op

revision = '0007_workflow_artifacts'
down_revision = '0006_workflow_runs'
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table('workflow_run_artifacts',
        sa.Column('run_id', sa.String(36), sa.ForeignKey('workflow_runs.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('id', sa.String(120), primary_key=True),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.String(120), nullable=False),
        sa.Column('execution_id', sa.String(120), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.UniqueConstraint('run_id', 'ordinal', name='uq_workflow_artifact_ordinal'))
    op.create_index('ix_workflow_artifacts_node', 'workflow_run_artifacts', ['run_id', 'node_id', 'ordinal'])
    op.create_index('ix_workflow_artifacts_execution', 'workflow_run_artifacts', ['run_id', 'execution_id', 'ordinal'])
    runs = sa.table('workflow_runs', sa.column('id', sa.String), sa.column('payload', sa.JSON))
    connection = op.get_bind()
    for identifier, payload in connection.execute(sa.select(runs.c.id, runs.c.payload)).fetchall():
        artifacts = payload.get('artifacts', [])
        if artifacts:
            connection.execute(table.insert(), [{'run_id': identifier, 'id': a['id'], 'ordinal': i + 1,
                'node_id': a['nodeId'], 'execution_id': a.get('executionId'), 'payload': a} for i, a in enumerate(artifacts)])
        connection.execute(runs.update().where(runs.c.id == identifier).values(payload={**payload, 'artifacts': [], 'artifactCount': len(artifacts)}))


def downgrade():
    connection = op.get_bind()
    runs = sa.table('workflow_runs', sa.column('id', sa.String), sa.column('payload', sa.JSON))
    artifacts = sa.table('workflow_run_artifacts', sa.column('run_id', sa.String), sa.column('ordinal', sa.Integer), sa.column('payload', sa.JSON))
    for identifier, payload in connection.execute(sa.select(runs.c.id, runs.c.payload)).fetchall():
        values = list(connection.execute(sa.select(artifacts.c.payload).where(artifacts.c.run_id == identifier).order_by(artifacts.c.ordinal)).scalars())
        connection.execute(runs.update().where(runs.c.id == identifier).values(payload={**payload, 'artifacts': values}))
    op.drop_table('workflow_run_artifacts')
