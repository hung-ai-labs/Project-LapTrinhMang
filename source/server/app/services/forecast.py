"""On-demand hourly previews; never persist forecast values as observations."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx

from app.schemas.weather import ForecastOut

HOURLY_VARIABLES = "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"
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
        values = [hourly[key][index] for key in HOURLY_VARIABLES.split(",")]
        if any(value is None or isinstance(value, bool) for value in values):
            raise ForecastUnavailable("Missing forecast value")
        return ForecastOut(
            ward_id=ward_id, target_at=target, fetched_at=fetched_at,
            predicted_temperature=values[0], predicted_humidity=values[1],
            predicted_wind_speed=values[2], precipitation_mm=values[3],
        )
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
        try:
            async with asyncio.timeout(12):
                async with self.slots:
                    async with self.client.stream(
                        "GET", "https://api.open-meteo.com/v1/forecast",
                        params={
                            "latitude": latitude, "longitude": longitude,
                            "hourly": HOURLY_VARIABLES, "forecast_hours": 3,
                            "temperature_unit": "celsius", "wind_speed_unit": "kmh",
                            "precipitation_unit": "mm", "timeformat": "unixtime",
                            "timezone": "UTC",
                        },
                        headers={"User-Agent": "WeatherStream-Education/0.3"},
                    ) as response:
                        response.raise_for_status()
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                                raise ForecastUnavailable("Forecast response is too large")
                            body.extend(chunk)
                    return parse_hourly(ward_id, json.loads(body), target, self.clock())
        except (httpx.HTTPError, TimeoutError, ValueError, TypeError) as exc:
            raise ForecastUnavailable("Forecast provider unavailable") from exc

    async def aclose(self):
        tasks = tuple(self.inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
