from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NearestWardInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class NearestWardOutput(BaseModel):
    ward_id: str
    ward_name: str
    province_id: str
    province_name: str
    distance_km: float = Field(ge=0)
    match_type: Literal["nearest"] = "nearest"
