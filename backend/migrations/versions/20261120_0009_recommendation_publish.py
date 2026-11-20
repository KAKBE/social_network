"""drafts and scheduled publication

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-20 17:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recommendations",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="published"),
    )
    op.add_column("recommendations", sa.Column("publish_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("recommendations", "publish_at")
    op.drop_column("recommendations", "status")
