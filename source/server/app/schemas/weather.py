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


class FutureForecastUnits(BaseModel):
    temperature: Literal["°C"] = "°C"
    humidity: Literal["%"] = "%"
    wind_speed: Literal["km/h"] = "km/h"
    rainfall: Literal["mm/giờ"] = "mm/giờ"
    rain_probability: Literal["%"] = "%"
    rain: Literal["mm/giờ"] = "mm/giờ"
    showers: Literal["mm/giờ"] = "mm/giờ"


class FutureHourOut(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    time: AwareDatetime
    temperature: float | None = Field(default=None, ge=-60, le=65)
    humidity: float | None = Field(default=None, ge=0, le=100)
    wind_speed: float | None = Field(default=None, ge=0, le=500)
    rainfall: float | None = Field(default=None, ge=0, le=1000)
    rain_probability: float | None = Field(default=None, ge=0, le=100)
    rain: float | None = Field(default=None, ge=0, le=1000)
    showers: float | None = Field(default=None, ge=0, le=1000)
    weather_code: int | None = Field(default=None, ge=0, le=99)


class FutureForecastOut(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    ward_id: str
    ward_name: str
    province_id: str
    source: Literal["open-meteo"] = "open-meteo"
    data_kind: Literal["model_forecast"] = "model_forecast"
    is_project_ai: bool = False
    timezone: Literal["Asia/Ho_Chi_Minh"] = "Asia/Ho_Chi_Minh"
    retrieved_at: AwareDatetime
    days: Literal[7] = 7
    hours: int = Field(ge=0, le=168)
    interval_seconds: Literal[3600] = 3600
    units: FutureForecastUnits = Field(default_factory=FutureForecastUnits)
    hourly: list[FutureHourOut]


class HealthOut(BaseModel):
    status: str
    database: str
