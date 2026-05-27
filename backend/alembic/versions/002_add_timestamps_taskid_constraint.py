"""add timestamps, celery_task_id, unique constraint

Revision ID: 002
Revises: 001
Create Date: 2026-05-27

"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New timestamp columns on notes
    op.add_column('notes', sa.Column('processing_started_at', sa.DateTime(), nullable=True))
    op.add_column('notes', sa.Column('completed_at', sa.DateTime(), nullable=True))
    op.add_column('notes', sa.Column('failed_at', sa.DateTime(), nullable=True))
    # Celery task ID for traceability
    op.add_column('notes', sa.Column('celery_task_id', sa.String(), nullable=True))

    # DB-level unique constraint on extracted_tasks
    op.create_unique_constraint(
        'uq_task_per_note',
        'extracted_tasks',
        ['note_id', 'task_type', 'description']
    )


def downgrade() -> None:
    op.drop_constraint('uq_task_per_note', 'extracted_tasks', type_='unique')
    op.drop_column('notes', 'celery_task_id')
    op.drop_column('notes', 'failed_at')
    op.drop_column('notes', 'completed_at')
    op.drop_column('notes', 'processing_started_at')
