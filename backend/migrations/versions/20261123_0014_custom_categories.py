"""custom profile categories

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-23 23:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0014"
down_revision: Union[str, Sequence[str], None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "recommendations",
        "category",
        existing_type=sa.String(length=20),
        type_=sa.String(length=24),
        existing_nullable=True,
    )
    op.create_table(
        "profile_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=24), nullable=False),
        sa.UniqueConstraint("owner_id", "title", name="uq_profile_categories_owner_title"),
    )


def downgrade() -> None:
    op.drop_table("profile_categories")
    op.execute("UPDATE recommendations SET category = NULL WHERE char_length(category) > 20")
    op.alter_column(
        "recommendations",
        "category",
        existing_type=sa.String(length=24),
        type_=sa.String(length=20),
        existing_nullable=True,
    )
