import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.security import LOGIN_PATTERN, password_is_strong

PLACE_CATEGORIES = ("study", "food", "walk", "meet")


class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class RegisterIn(BaseModel):
    login: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    username: str | None = None

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not password_is_strong(value):
            raise ValueError("Пароль: от 12 символов, заглавные и строчные буквы, цифра и специальный символ")
        return value

    @field_validator("display_name")
    @classmethod
    def plain_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 or char in "<>" for char in value):
            raise ValueError("Недопустимые символы в никнейме")
        return value

    @field_validator("username")
    @classmethod
    def plain_username(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        if LOGIN_PATTERN.fullmatch(value) is None:
            raise ValueError("Username: 3–50 символов, латиница, цифры и _")
        return value


class TokenOut(BaseModel):
    token: str


class UserOut(BaseModel):
    id: int
    public_id: uuid.UUID
    username: str
    display_name: str


class MeOut(BaseModel):
    id: int
    public_id: uuid.UUID
    login: str
    username: str
    display_name: str
    surname: str = ""
    bio: str
    profile_visibility: str
    theme: str
    has_avatar: bool


class ProfilePerson(BaseModel):
    public_id: uuid.UUID
    username: str
    display_name: str
    has_avatar: bool


class ProfileOut(BaseModel):
    public_id: uuid.UUID
    username: str
    display_name: str
    surname: str = ""
    bio: str
    has_avatar: bool
    is_self: bool = False
    relation: Literal["self", "none", "outgoing", "incoming", "friend"] = "none"
    is_close: bool = False
    friend_count: int | None = None
    mutual_count: int | None = None
    friends: list[ProfilePerson] = Field(default_factory=list)
    mutual: list[ProfilePerson] = Field(default_factory=list)


class UserSearchOut(BaseModel):
    public_id: uuid.UUID
    username: str
    display_name: str
    relation: Literal["none", "outgoing", "incoming", "friend"]
    is_close: bool = False


class FriendOut(BaseModel):
    id: int
    username: str
    display_name: str
    is_close: bool


class CloseFriendIn(BaseModel):
    close: bool


class FriendRequestIn(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")


class FriendRequestOut(BaseModel):
    id: int
    public_id: uuid.UUID
    username: str
    display_name: str


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    surname: str | None = Field(default=None, max_length=100)
    username: str | None = None
    bio: str | None = Field(default=None, max_length=500)
    profile_visibility: Literal["everyone", "friends"] | None = None
    theme: Literal["light", "dark"] | None = None

    @field_validator("display_name")
    @classmethod
    def plain_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or any(ord(char) < 32 or char in "<>" for char in value):
            raise ValueError("Недопустимые символы в никнейме")
        return value

    @field_validator("surname")
    @classmethod
    def plain_surname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if any(ord(char) < 32 or char in "<>" for char in value):
            raise ValueError("Недопустимые символы в фамилии")
        return value or None

    @field_validator("username")
    @classmethod
    def plain_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if LOGIN_PATTERN.fullmatch(value) is None:
            raise ValueError("Username: 3–50 символов, латиница, цифры и _")
        return value

    @field_validator("bio")
    @classmethod
    def plain_bio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if any((ord(char) < 32 and char not in "\n\t") or char in "<>" for char in value):
            raise ValueError("Недопустимые символы в описании")
        return value.strip()


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)
    password_repeat: str = Field(min_length=1, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not password_is_strong(value):
            raise ValueError("Пароль: от 12 символов, заглавные и строчные буквы, цифра и специальный символ")
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordChangeIn":
        if self.password != self.password_repeat:
            raise ValueError("Пароли не совпадают")
        return self


class PlaceOut(BaseModel):
    id: int
    name: str
    address: str
    lat: float
    lon: float
    city: str = ""


class PhotoOut(BaseModel):
    id: int


class RecommendationOut(BaseModel):
    id: int
    text: str
    created_at: datetime
    author: UserOut
    place: PlaceOut
    is_own: bool
    visibility: str
    liked: bool
    like_count: int
    status: str
    category: str = ""
    photos: list[PhotoOut] = Field(default_factory=list)
    audience: list[str] = Field(default_factory=list)
    on_map: bool = False


class RecommendationIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(default="", max_length=300)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    text: str = Field(min_length=1, max_length=2000)
    point_corrected: bool = False
    visibility: Literal["friends", "close", "allow", "deny", "everyone"] = "friends"
    category: Literal["study", "food", "walk", "meet"] | None = None
    audience: list[str] = Field(default_factory=list, max_length=50)
    draft: bool = False

    @field_validator("category", mode="before")
    @classmethod
    def blank_category(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return value
    publish_at: datetime | None = None
    list_id: int | None = None
    city: str = Field(default="", max_length=120)

    @field_validator("audience")
    @classmethod
    def plain_usernames(cls, value: list[str]) -> list[str]:
        for name in value:
            if not LOGIN_PATTERN.fullmatch(name):
                raise ValueError("Некорректное имя пользователя")
        return value

    @field_validator("city")
    @classmethod
    def plain_city(cls, value: str) -> str:
        value = " ".join(value.split())
        if any(ch in "<>" for ch in value):
            raise ValueError("Некорректный город")
        return value


class RecommendationUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=2000)
    visibility: Literal["friends", "close", "allow", "deny", "everyone"] = "friends"
    category: Literal["study", "food", "walk", "meet"] | None = None
    audience: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("category", mode="before")
    @classmethod
    def blank_category(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return value

    @field_validator("name", "text")
    @classmethod
    def filled_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Заполните поле")
        return value

    @field_validator("audience")
    @classmethod
    def plain_usernames(cls, value: list[str]) -> list[str]:
        for name in value:
            if not LOGIN_PATTERN.fullmatch(name):
                raise ValueError("Некорректное имя пользователя")
        return value


class GeocodeIn(BaseModel):
    query: str = Field(min_length=3, max_length=300)


class GeocodeItemOut(BaseModel):
    display_name: str
    lat: float
    lon: float
    city: str = ""


class GeocodeOut(BaseModel):
    results: list[GeocodeItemOut]
    cached: bool


class ReverseIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class ReverseOut(BaseModel):
    address: str
    city: str = ""
    cached: bool


class PlaceListIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class SavedPlaceOut(BaseModel):
    id: int | None
    item_id: int
    name: str
    address: str
    lat: float
    lon: float
    city: str = ""
    limited: bool = False


class PlaceListOut(BaseModel):
    id: int
    title: str
    places: list[SavedPlaceOut]


class AddPlaceIn(BaseModel):
    place_id: int


class PerfSampleIn(BaseModel):
    series: str = Field(min_length=1, max_length=100)
    seq: int = Field(ge=0)
    total_ms: float = Field(ge=0)
    dom_ready_ms: float = Field(ge=0)
    feed_ms: float = Field(ge=0)
    server_ms: float | None = None
    markers: int = Field(ge=0)
    navigation_type: str = Field(max_length=30)


class ClientConfigOut(BaseModel):
    tile_url: str
    tile_attribution: str


class NotificationOut(BaseModel):
    id: int
    recommendation_id: int
    author_name: str
    place_name: str
    read: bool
    created_at: datetime


class NotificationListOut(BaseModel):
    unread: int
    items: list[NotificationOut]
