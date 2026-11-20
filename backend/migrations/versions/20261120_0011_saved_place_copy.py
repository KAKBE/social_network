"""saved place copy survives a hidden or deleted recommendation

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-20 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE place_list_items ADD COLUMN id SERIAL")
    op.drop_constraint("place_list_items_pkey", "place_list_items", type_="primary")
    op.create_primary_key("place_list_items_pkey", "place_list_items", ["id"])
    op.add_column("place_list_items", sa.Column("name", sa.String(length=200), nullable=False, server_default=""))
    op.add_column("place_list_items", sa.Column("address", sa.String(length=300), nullable=False, server_default=""))
    op.add_column("place_list_items", sa.Column("lat", sa.Float(), nullable=True))
    op.add_column("place_list_items", sa.Column("lon", sa.Float(), nullable=True))
    op.execute(
        """
        UPDATE place_list_items AS item
        SET name = place.name, address = place.address, lat = place.lat, lon = place.lon
        FROM places AS place
        WHERE place.id = item.place_id
        """
    )
    op.alter_column("place_list_items", "lat", nullable=False)
    op.alter_column("place_list_items", "lon", nullable=False)
    op.drop_constraint("place_list_items_place_id_fkey", "place_list_items", type_="foreignkey")
    op.alter_column("place_list_items", "place_id", nullable=True)
    op.create_foreign_key(
        "place_list_items_place_id_fkey",
        "place_list_items",
        "places",
        ["place_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint("uq_place_list_items_list_place", "place_list_items", ["list_id", "place_id"])
    op.alter_column("place_list_items", "name", server_default=None)
    op.alter_column("place_list_items", "address", server_default=None)


def downgrade() -> None:
    op.drop_constraint("uq_place_list_items_list_place", "place_list_items", type_="unique")
    op.drop_constraint("place_list_items_place_id_fkey", "place_list_items", type_="foreignkey")
    op.execute("DELETE FROM place_list_items WHERE place_id IS NULL")
    op.alter_column("place_list_items", "place_id", nullable=False)
    op.create_foreign_key(
        "place_list_items_place_id_fkey",
        "place_list_items",
        "places",
        ["place_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("place_list_items_pkey", "place_list_items", type_="primary")
    op.create_primary_key("place_list_items_pkey", "place_list_items", ["list_id", "place_id"])
    op.drop_column("place_list_items", "lon")
    op.drop_column("place_list_items", "lat")
    op.drop_column("place_list_items", "address")
    op.drop_column("place_list_items", "name")
    op.drop_column("place_list_items", "id")
