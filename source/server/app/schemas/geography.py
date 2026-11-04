from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProvinceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class WardOut(ProvinceOut):
    province_id: str
    administrative_type: str | None
    latitude: float | None
    longitude: float | None


class NearestWardInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class NearestWardOut(BaseModel):
    ward: WardOut
    province: ProvinceOut
    distance_km: float = Field(ge=0)
    match_type: Literal["nearest"] = "nearest"
