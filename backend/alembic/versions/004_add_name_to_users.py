"""add name to users

Revision ID: 004
Revises: 003
Create Date: 2026-05-27

"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # nullable=True first so existing rows don't fail, then backfill, then set not null
    op.add_column('users', sa.Column('name', sa.String(), nullable=True))
    op.execute("UPDATE users SET name = split_part(email, '@', 1) WHERE name IS NULL")
    op.alter_column('users', 'name', nullable=False)


def downgrade() -> None:
    op.drop_column('users', 'name')
