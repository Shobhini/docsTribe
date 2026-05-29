"""add users table and user_id to notes

Revision ID: 003
Revises: 002
Create Date: 2026-05-27

"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.add_column('notes', sa.Column('user_id', sa.String(), nullable=True))
    op.create_foreign_key('fk_notes_user_id', 'notes', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_notes_user_id', 'notes', type_='foreignkey')
    op.drop_column('notes', 'user_id')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
