"""friend requests

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-20 16:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "friend_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("from_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_friend_requests_from_user_id", "friend_requests", ["from_user_id"])
    op.create_index("ix_friend_requests_to_user_id", "friend_requests", ["to_user_id"])


def downgrade() -> None:
    op.drop_index("ix_friend_requests_to_user_id", table_name="friend_requests")
    op.drop_index("ix_friend_requests_from_user_id", table_name="friend_requests")
    op.drop_table("friend_requests")
