"""recommendation visibility and close friends

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-20 16:20:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recommendations",
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default="friends"),
    )
    op.create_table(
        "close_friends",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("friend_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "recommendation_audience",
        sa.Column(
            "recommendation_id",
            sa.Integer(),
            sa.ForeignKey("recommendations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("recommendation_audience")
    op.drop_table("close_friends")
    op.drop_column("recommendations", "visibility")
