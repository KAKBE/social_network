"""place city and recommendation views

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-20 17:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("places", sa.Column("city", sa.String(length=120), nullable=False, server_default=""))
    op.create_table(
        "recommendation_views",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "recommendation_id",
            sa.Integer(),
            sa.ForeignKey("recommendations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("recommendation_views")
    op.drop_column("places", "city")
