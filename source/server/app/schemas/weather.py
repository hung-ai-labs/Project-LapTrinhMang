from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

City = Literal["hanoi", "danang", "hcm"]


class ObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    event_id: UUID
    city: City
    temperature: float = Field(ge=-60, le=65)
    humidity: float = Field(ge=0, le=100)
    wind_speed: float = Field(ge=0, le=500, description="km/h")
    rainfall: float = Field(ge=0, le=1000, description="mm/h")
    source: Literal["simulator", "provider"] = "simulator"
    observed_at: AwareDatetime


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    city: str
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
    city: str
    method: Literal["persistence_baseline"] = "persistence_baseline"
    is_ai: bool = False
    message: str = "Baseline giữ nguyên quan sát mới nhất; chưa tích hợp mô hình AI."
    predicted_temperature: float
    target_at: datetime
    based_on: str


class HealthOut(BaseModel):
    status: str
    database: str


class CitiesOut(BaseModel):
    id: str
    name: str
