"""optional surname and recommendation category

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-23 21:15:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("surname", sa.String(length=100), nullable=True))
    op.add_column("recommendations", sa.Column("category", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("recommendations", "category")
    op.drop_column("users", "surname")
