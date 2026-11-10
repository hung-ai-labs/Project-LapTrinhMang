"""Provider forecast is separate from observations and the project's baseline."""

import asyncio
import time
from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field

LOCATIONS = {
    "hanoi": (21.0285, 105.8542),
    "danang": (16.0544, 108.2022),
    "hcm": (10.8231, 106.6297),
}
HOURLY = (
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "precipitation",
    "precipitation_probability",
)
DAILY = (
    "temperature_2m_min",
    "temperature_2m_max",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
)


class HourForecast(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    time: datetime
    temperature: float | None
    humidity: float | None = Field(ge=0, le=100)
    wind_speed: float | None = Field(ge=0)
    precipitation: float | None = Field(ge=0)
    rain_probability: float | None = Field(ge=0, le=100)


class DayForecast(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    date: date
    temperature_min: float | None
    temperature_max: float | None
    precipitation_sum: float | None = Field(ge=0)
    rain_probability_max: float | None = Field(ge=0, le=100)
    wind_speed_max: float | None = Field(ge=0)


class ProviderForecast(BaseModel):
    city: str
    source: Literal["open-meteo"] = "open-meteo"
    is_project_ai: bool = False
    retrieved_at: datetime
    timezone: str = "Asia/Ho_Chi_Minh"
    hourly: list[HourForecast]
    daily: list[DayForecast]


def parse_forecast(city, payload):
    expected = {
        "temperature_2m": "°C",
        "relative_humidity_2m": "%",
        "wind_speed_10m": "km/h",
        "precipitation": "mm",
        "precipitation_probability": "%",
    }
    daily_units = {
        "temperature_2m_min": "°C",
        "temperature_2m_max": "°C",
        "precipitation_sum": "mm",
        "precipitation_probability_max": "%",
        "wind_speed_10m_max": "km/h",
    }
    for name, units in [("hourly", expected), ("daily", daily_units)]:
        block = payload[name]
        if not block["time"]:
            raise ValueError("Empty forecast")
        for key, unit in units.items():
            if payload[name + "_units"][key] != unit:
                raise ValueError("Unexpected forecast units")
            if len(block[key]) != len(block["time"]):
                raise ValueError("Mismatched forecast arrays")
    h, d = payload["hourly"], payload["daily"]
    return ProviderForecast(
        city=city,
        retrieved_at=datetime.now(UTC),
        hourly=[
            HourForecast(
                time=datetime.fromtimestamp(t, UTC),
                temperature=h[HOURLY[0]][i],
                humidity=h[HOURLY[1]][i],
                wind_speed=h[HOURLY[2]][i],
                precipitation=h[HOURLY[3]][i],
                rain_probability=h[HOURLY[4]][i],
            )
            for i, t in enumerate(h["time"])
        ],
        daily=[
            DayForecast(
                date=datetime.fromtimestamp(t, UTC).astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date(),
                temperature_min=d[DAILY[0]][i],
                temperature_max=d[DAILY[1]][i],
                precipitation_sum=d[DAILY[2]][i],
                rain_probability_max=d[DAILY[3]][i],
                wind_speed_max=d[DAILY[4]][i],
            )
            for i, t in enumerate(d["time"])
        ],
    )


async def fetch_forecast(city, days):
    lat, lon = LOCATIONS[city]
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": ",".join(HOURLY),
                "daily": ",".join(DAILY),
                "forecast_days": days,
                "timezone": "Asia/Ho_Chi_Minh",
                "timeformat": "unixtime",
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "precipitation_unit": "mm",
            },
        )
        response.raise_for_status()
        return parse_forecast(city, response.json())


_cache = {}
_lock = asyncio.Lock()


async def get_forecast(city, days):
    key = (city, days)
    async with _lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < 900:
            return cached[1]
        data = await fetch_forecast(city, days)
        _cache[key] = (time.monotonic(), data)
        return data
