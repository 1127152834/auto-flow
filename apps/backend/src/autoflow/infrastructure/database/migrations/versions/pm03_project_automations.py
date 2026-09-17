"""Persist project automation configuration without duplicating workflows."""

import sqlalchemy as sa
from alembic import op

revision = 'pm03_project_automations'
down_revision = '0011_workflow_runtime_contracts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'project_automations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('workflow_id', sa.String(36), sa.ForeignKey('workflow_documents.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('name_key', sa.Text(), nullable=False),
        sa.Column('search_text', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('management_revision', sa.Integer(), nullable=False),
        sa.Column('input_plan', sa.JSON(), nullable=False),
        sa.Column('parameter_schema', sa.JSON(), nullable=False),
        sa.Column('environment_policy', sa.JSON(), nullable=False),
        sa.Column('run_policy', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('workflow_id', name='uq_project_automations_workflow'),
        sa.UniqueConstraint('project_id', 'name_key', name='uq_project_automations_project_name'),
    )
    op.create_index('ix_project_automations_project_updated', 'project_automations', ['project_id', 'updated_at'])


def downgrade() -> None:
    if op.get_bind().execute(sa.text('SELECT 1 FROM project_automations LIMIT 1')).first():
        raise RuntimeError('Automation configuration exists; restore a backup instead of discarding it.')
    op.drop_index('ix_project_automations_project_updated', table_name='project_automations')
    op.drop_table('project_automations')
