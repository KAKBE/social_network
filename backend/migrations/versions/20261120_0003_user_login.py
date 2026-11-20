"""user login and profile fields

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-20 15:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("public_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE users SET public_id = gen_random_uuid()")
    op.alter_column("users", "public_id", nullable=False)
    op.create_unique_constraint("uq_users_public_id", "users", ["public_id"])

    op.add_column("users", sa.Column("login", sa.String(length=50), nullable=True))
    op.execute("UPDATE users SET login = username")
    op.alter_column("users", "login", nullable=False)
    op.create_unique_constraint("uq_users_login", "users", ["login"])

    op.add_column("users", sa.Column("bio", sa.Text(), server_default=sa.text("''"), nullable=False))
    op.add_column(
        "users",
        sa.Column("profile_visibility", sa.String(length=20), server_default="everyone", nullable=False),
    )
    op.add_column("users", sa.Column("theme", sa.String(length=10), server_default="light", nullable=False))


def downgrade() -> None:
    op.drop_column("users", "theme")
    op.drop_column("users", "profile_visibility")
    op.drop_column("users", "bio")
    op.drop_constraint("uq_users_login", "users", type_="unique")
    op.drop_column("users", "login")
    op.drop_constraint("uq_users_public_id", "users", type_="unique")
    op.drop_column("users", "public_id")
