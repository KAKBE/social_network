from datetime import datetime

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    token: str


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str


class PlaceOut(BaseModel):
    id: int
    name: str
    address: str
    lat: float
    lon: float


class RecommendationOut(BaseModel):
    id: int
    text: str
    created_at: datetime
    author: UserOut
    place: PlaceOut
    is_own: bool


class RecommendationIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(default="", max_length=300)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    text: str = Field(min_length=1, max_length=2000)
    point_corrected: bool = False


class GeocodeIn(BaseModel):
    query: str = Field(min_length=3, max_length=300)


class GeocodeItemOut(BaseModel):
    display_name: str
    lat: float
    lon: float


class GeocodeOut(BaseModel):
    results: list[GeocodeItemOut]
    cached: bool


class PlaceListIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class PlaceListOut(BaseModel):
    id: int
    title: str
    places: list[PlaceOut]


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
