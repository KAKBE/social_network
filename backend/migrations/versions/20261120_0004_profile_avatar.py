"""profile avatar and dark theme default

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-20 15:50:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_path", sa.String(length=80), nullable=True))
    # 0003 stored "light" before a theme could be chosen. The running sample is dark.
    op.execute("UPDATE users SET theme = 'dark' WHERE theme = 'light'")
    op.alter_column("users", "theme", server_default="dark")


def downgrade() -> None:
    op.alter_column("users", "theme", server_default="light")
    op.drop_column("users", "avatar_path")
