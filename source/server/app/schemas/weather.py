from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    event_id: UUID
    ward_id: str = Field(min_length=1, max_length=20)
    temperature: float = Field(ge=-60, le=65)
    humidity: float = Field(ge=0, le=100)
    wind_speed: float = Field(ge=0, le=500, description="km/h")
    rainfall: float = Field(ge=0, le=1000, description="mm/h")
    source: Literal["simulator", "provider"] = "simulator"
    observed_at: AwareDatetime


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    ward_id: str
    temperature: float
    humidity: float
    wind_speed: float
    rainfall: float
    source: str
    observed_at: datetime


class Alert(BaseModel):
    code: str
    severity: Literal["warning"] = "warning"
    message: str


class WeatherEvent(BaseModel):
    type: Literal["weather.update"] = "weather.update"
    observation: ObservationOut
    alerts: list[Alert]


class ForecastOut(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    ward_id: str
    provider: Literal["open_meteo"] = "open_meteo"
    method: Literal["open_meteo_hourly"] = "open_meteo_hourly"
    data_kind: Literal["model_forecast"] = "model_forecast"
    target_at: AwareDatetime
    fetched_at: AwareDatetime
    predicted_temperature: float = Field(ge=-60, le=65)
    predicted_humidity: float = Field(ge=0, le=100)
    predicted_wind_speed: float = Field(ge=0, le=500)
    precipitation_mm: float = Field(ge=0)
    interval_seconds: Literal[3600] = 3600


class HealthOut(BaseModel):
    status: str
    database: str
