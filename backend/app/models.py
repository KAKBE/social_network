from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(200))


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Friendship(Base):
    """Stored in both directions so that a friend lookup is a single indexed filter."""

    __tablename__ = "friendships"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    friend_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )


class Place(Base):
    __tablename__ = "places"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300), default="")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # ADR-4 metric: the author moved the geocoder's point on the map after choosing an address.
    point_corrected: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (Index("ix_recommendations_author_created", "author_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    author: Mapped[User] = relationship()
    place: Mapped[Place] = relationship()


class PlaceList(Base):
    __tablename__ = "place_lists"
    __table_args__ = (UniqueConstraint("owner_id", "title"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(100))


class PlaceListItem(Base):
    __tablename__ = "place_list_items"

    list_id: Mapped[int] = mapped_column(
        ForeignKey("place_lists.id", ondelete="CASCADE"), primary_key=True
    )
    place_id: Mapped[int] = mapped_column(
        ForeignKey("places.id", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    place: Mapped[Place] = relationship()


class PerfSample(Base):
    """One measurement of RAT criterion K2, sent by the client after the map markers are painted."""

    __tablename__ = "perf_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    series: Mapped[str] = mapped_column(String(100))
    seq: Mapped[int]
    total_ms: Mapped[float] = mapped_column(Float)
    dom_ready_ms: Mapped[float] = mapped_column(Float)
    feed_ms: Mapped[float] = mapped_column(Float)
    server_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    markers: Mapped[int]
    navigation_type: Mapped[str] = mapped_column(String(30))
    user_agent: Mapped[str] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GeocodeCacheEntry(Base):
    __tablename__ = "geocode_cache"

    query: Mapped[str] = mapped_column(String(300), primary_key=True)
    results: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
