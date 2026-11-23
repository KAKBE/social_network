import uuid
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
    Uuid,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, default=uuid.uuid4)
    login: Mapped[str] = mapped_column(String(50), unique=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    surname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    bio: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    profile_visibility: Mapped[str] = mapped_column(String(20), default="everyone", server_default="everyone")
    theme: Mapped[str] = mapped_column(String(10), default="dark", server_default="dark")
    avatar_path: Mapped[str | None] = mapped_column(String(80), nullable=True)


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


class FriendRequest(Base):
    __tablename__ = "friend_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    from_user: Mapped[User] = relationship(foreign_keys=[from_user_id])


class CloseFriend(Base):
    """A friend the user marked as close. The mark belongs to the user, not the pair."""

    __tablename__ = "close_friends"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    friend_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


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
    city: Mapped[str] = mapped_column(String(120), default="", server_default=text("''"))


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (Index("ix_recommendations_author_created", "author_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(24), nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="friends", server_default="friends")
    status: Mapped[str] = mapped_column(String(20), default="published", server_default="published")
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    author: Mapped[User] = relationship()
    place: Mapped[Place] = relationship()


class RecommendationAudience(Base):
    """Friends included in an allow list or excluded by a deny list."""

    __tablename__ = "recommendation_audience"

    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class RecommendationLike(Base):
    __tablename__ = "recommendation_likes"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), primary_key=True
    )


class RecommendationView(Base):
    """A recommendation becomes seen when this user opens its page."""

    __tablename__ = "recommendation_views"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), primary_key=True
    )
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RecommendationPhoto(Base):
    __tablename__ = "recommendation_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id", ondelete="CASCADE"), index=True)
    stored_name: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(default=0)


class ProfileCategory(Base):
    """A category the author added on their own profile. Built-in labels are not rows here."""

    __tablename__ = "profile_categories"
    __table_args__ = (UniqueConstraint("owner_id", "title"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(24))


class PlaceList(Base):
    __tablename__ = "place_lists"
    __table_args__ = (UniqueConstraint("owner_id", "title"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(100))


class PlaceListItem(Base):
    """A saved place. The name and point stay after the recommendation is hidden or deleted."""

    __tablename__ = "place_list_items"
    __table_args__ = (UniqueConstraint("list_id", "place_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("place_lists.id", ondelete="CASCADE"))
    place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300), default="")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    place: Mapped[Place | None] = relationship()


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


class NotificationJob(Base):
    """One fan-out of a published recommendation. The id stays stable across claim and retry."""

    __tablename__ = "notification_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", server_default="queued")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    process_count: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FriendNotification(Base):
    """A friend can receive the same recommendation only once, even if the job is claimed twice."""

    __tablename__ = "friend_notifications"
    __table_args__ = (UniqueConstraint("user_id", "recommendation_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id", ondelete="CASCADE"))
    job_id: Mapped[int] = mapped_column(ForeignKey("notification_jobs.id", ondelete="CASCADE"))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
