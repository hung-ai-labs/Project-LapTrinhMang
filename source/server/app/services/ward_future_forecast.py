"""Seven-day hourly forecast for a ward; never persisted as observations."""

import asyncio
import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx

from app.schemas.weather import FutureForecastOut, FutureHourOut
from app.services.forecast import next_hour
from app.services.open_meteo import fetch_json, hourly_series, number

VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
FORECAST_DAYS = 7
FORECAST_HOURS = FORECAST_DAYS * 24
PROVIDER_DAYS = FORECAST_DAYS + 1
CACHE_TTL_SECONDS = 900
MAX_RESPONSE_BYTES = 256 * 1024
HOURLY_VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "rain",
    "precipitation_probability",
    "showers",
    "weather_code",
    "wind_speed_10m",
)
EXPECTED_UNITS = {
    "temperature_2m": "°C",
    "relative_humidity_2m": "%",
    "precipitation": "mm",
    "rain": "mm",
    "precipitation_probability": "%",
    "showers": "mm",
    "weather_code": "wmo code",
    "wind_speed_10m": "km/h",
}


class FutureForecastUnavailable(ValueError):
    pass


def _optional_number(value, minimum, maximum):
    if value is None:
        return None
    try:
        return number(value, minimum, maximum)
    except ValueError as exc:
        raise FutureForecastUnavailable("Invalid forecast value") from exc


def _weather_code(value):
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= 99:
        raise FutureForecastUnavailable("Invalid weather code")
    return value


def parse_future_forecast(ward_id, ward_name, province_id, payload, now):
    times, hourly = hourly_series(payload, EXPECTED_UNITS, FutureForecastUnavailable)
    start = next_hour(now)
    rows = []
    for index, timestamp in enumerate(times):
        target = datetime.fromtimestamp(timestamp, UTC).astimezone(VIETNAM_TZ)
        if target < start:
            continue
        rows.append(
            FutureHourOut(
                time=target,
                temperature=_optional_number(hourly["temperature_2m"][index], -60, 65),
                humidity=_optional_number(hourly["relative_humidity_2m"][index], 0, 100),
                wind_speed=_optional_number(hourly["wind_speed_10m"][index], 0, 500),
                rainfall=_optional_number(hourly["precipitation"][index], 0, 1000),
                rain_probability=_optional_number(
                    hourly["precipitation_probability"][index], 0, 100
                ),
                rain=_optional_number(hourly["rain"][index], 0, 1000),
                showers=_optional_number(hourly["showers"][index], 0, 1000),
                weather_code=_weather_code(hourly["weather_code"][index]),
            )
        )
        if len(rows) == FORECAST_HOURS:
            break
    if not rows:
        raise FutureForecastUnavailable("No future forecast")
    return FutureForecastOut(
        ward_id=ward_id,
        ward_name=ward_name,
        province_id=province_id,
        retrieved_at=now.astimezone(VIETNAM_TZ),
        hours=len(rows),
        hourly=rows,
    )


class OpenMeteoWardFuture:
    def __init__(self, client: httpx.AsyncClient, *, clock=None):
        self.client = client
        self.clock = clock or (lambda: datetime.now(UTC))
        self.cache: dict[tuple[str, float, float], tuple[float, FutureForecastOut]] = {}
        self.lock = asyncio.Lock()

    async def get(self, ward_id, ward_name, province_id, latitude, longitude):
        key = (ward_id, latitude, longitude)
        async with self.lock:
            cached = self.cache.get(key)
            if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
                return cached[1]
            now = self.clock()
            now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
            data = await self.fetch(ward_id, ward_name, province_id, latitude, longitude, now)
            self.cache[key] = (time.monotonic(), data)
            return data

    async def fetch(self, ward_id, ward_name, province_id, latitude, longitude, now):
        payload = await fetch_json(
            self.client,
            {
                "latitude": latitude,
                "longitude": longitude,
                "hourly": ",".join(HOURLY_VARIABLES),
                "forecast_days": PROVIDER_DAYS,
                "timezone": "Asia/Ho_Chi_Minh",
                "timeformat": "unixtime",
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "precipitation_unit": "mm",
            },
            max_bytes=MAX_RESPONSE_BYTES,
            error_cls=FutureForecastUnavailable,
        )
        return parse_future_forecast(ward_id, ward_name, province_id, payload, now)
