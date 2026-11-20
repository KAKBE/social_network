"""recommendation photos

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-20 16:50:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendation_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recommendation_id",
            sa.Integer(),
            sa.ForeignKey("recommendations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stored_name", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_recommendation_photos_recommendation_id", "recommendation_photos", ["recommendation_id"])


def downgrade() -> None:
    op.drop_index("ix_recommendation_photos_recommendation_id", table_name="recommendation_photos")
    op.drop_table("recommendation_photos")
