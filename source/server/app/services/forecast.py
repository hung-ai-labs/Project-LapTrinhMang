"""On-demand hourly previews; never persist forecast values as observations."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx

from app.schemas.weather import ForecastOut
from app.services.open_meteo import WEATHER_VARIABLES, fetch_json

MAX_RESPONSE_BYTES = 256 * 1024


class ForecastUnavailable(ValueError):
    pass


def next_hour(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def parse_hourly(ward_id: str, payload: dict, target: datetime, fetched_at: datetime):
    expected = {
        "time": "unixtime", "temperature_2m": "°C", "relative_humidity_2m": "%",
        "wind_speed_10m": "km/h", "precipitation": "mm",
    }
    try:
        units, hourly = payload["hourly_units"], payload["hourly"]
        if any(units.get(key) != unit for key, unit in expected.items()):
            raise ForecastUnavailable("Unexpected forecast units")
        times = hourly["time"]
        if not isinstance(times, list) or any(type(value) is not int for value in times):
            raise ForecastUnavailable("Invalid forecast timestamps")
        index = times.index(int(target.timestamp()))
        values = [hourly[key][index] for key in WEATHER_VARIABLES.split(",")]
        if any(value is None or isinstance(value, bool) for value in values):
            raise ForecastUnavailable("Missing forecast value")
        return ForecastOut(
            ward_id=ward_id, target_at=target, fetched_at=fetched_at,
            predicted_temperature=values[0], predicted_humidity=values[1],
            predicted_wind_speed=values[2], precipitation_mm=values[3],
        )
    except ForecastUnavailable:
        raise
    except (AttributeError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise ForecastUnavailable("Invalid or unavailable hourly forecast") from exc


class OpenMeteoForecast:
    """Share only requests still in flight; later previews always fetch again."""

    def __init__(self, client: httpx.AsyncClient, *, clock=None, max_pending=32):
        self.client = client
        self.clock = clock or (lambda: datetime.now(UTC))
        self.max_pending = max_pending
        self.inflight: dict[tuple, asyncio.Task] = {}
        self.slots = asyncio.Semaphore(2)

    async def get(self, ward_id: str, latitude: float, longitude: float) -> ForecastOut:
        for _ in range(2):
            target = next_hour(self.clock())
            key = (ward_id, latitude, longitude, int(target.timestamp()))
            task = self.inflight.get(key)
            if task is not None and task.done():
                self.inflight.pop(key, None)
                task = None
            if task is None:
                if len(self.inflight) >= self.max_pending:
                    raise ForecastUnavailable("Forecast queue is full")
                task = asyncio.create_task(self._load(key, target))
                self.inflight[key] = task
                task.add_done_callback(
                    lambda done, request_key=key: self._finished(request_key, done)
                )
            result = await asyncio.shield(task)
            if result.target_at > self.clock():
                return result
        raise ForecastUnavailable("Forecast target expired during request")

    def _finished(self, key, task):
        if self.inflight.get(key) is task:
            self.inflight.pop(key, None)
        if not task.cancelled():
            task.exception()

    async def _load(self, key, target):
        ward_id, latitude, longitude, _ = key
        async with self.slots:
            payload = await fetch_json(
                self.client,
                {
                    "latitude": latitude, "longitude": longitude,
                    "hourly": WEATHER_VARIABLES, "forecast_hours": 3,
                    "temperature_unit": "celsius", "wind_speed_unit": "kmh",
                    "precipitation_unit": "mm", "timeformat": "unixtime",
                    "timezone": "UTC",
                },
                max_bytes=MAX_RESPONSE_BYTES,
                error_cls=ForecastUnavailable,
            )
        return parse_hourly(ward_id, payload, target, self.clock())

    async def aclose(self):
        tasks = tuple(self.inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
