"""Independent recording drafts and non-consuming, ordered steps."""
import sqlalchemy as sa
from alembic import op

revision = '0009_workflow_recordings'
down_revision = '0008_workflow_debug'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('workflow_recordings', sa.Column('id', sa.String(36), primary_key=True), sa.Column('payload', sa.JSON(), nullable=False))
    op.create_table('workflow_recording_steps',
                    sa.Column('recording_id', sa.String(36), sa.ForeignKey('workflow_recordings.id', ondelete='CASCADE'), primary_key=True),
                    sa.Column('seq', sa.Integer(), primary_key=True), sa.Column('id', sa.String(36), nullable=False),
                    sa.Column('position', sa.Integer(), nullable=False), sa.Column('payload', sa.JSON(), nullable=False),
                    sa.UniqueConstraint('recording_id', 'id'))
    op.create_table('workflow_recording_commands',
                    sa.Column('recording_id', sa.String(36), sa.ForeignKey('workflow_recordings.id', ondelete='CASCADE'), primary_key=True),
                    sa.Column('id', sa.String(36), primary_key=True), sa.Column('request_hash', sa.String(64), nullable=False),
                    sa.Column('payload', sa.JSON(), nullable=False))


def downgrade():
    op.drop_table('workflow_recording_commands')
    op.drop_table('workflow_recording_steps')
    op.drop_table('workflow_recordings')
