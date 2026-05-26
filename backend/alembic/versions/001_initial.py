"""initial

Revision ID: 001
Revises:
Create Date: 2026-05-26

"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types first, skip if already exist (created by SQLAlchemy auto-create)
    notestatus = sa.Enum('pending', 'processing', 'completed', 'failed', name='notestatus')
    tasktype = sa.Enum('lab_test', 'radiology', 'followup', name='tasktype')
    notestatus.create(op.get_bind(), checkfirst=True)
    tasktype.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'notes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', name='notestatus', create_type=False), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'extracted_tasks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('note_id', sa.String(), nullable=False),
        sa.Column('task_type', sa.Enum('lab_test', 'radiology', 'followup', name='tasktype', create_type=False), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['note_id'], ['notes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('extracted_tasks')
    op.drop_table('notes')
    sa.Enum(name='tasktype').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='notestatus').drop(op.get_bind(), checkfirst=False)
