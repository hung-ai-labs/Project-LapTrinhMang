"""On-demand Open-Meteo current values."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

import httpx
from sqlalchemy import select

from app.db import Observation
from app.db.session import Session
from app.schemas.weather import ObservationInput, WeatherEvent
from app.services.events import event_from_record
from app.services.ingestion import ingest
from app.services.open_meteo import WEATHER_VARIABLES, fetch_json, number

INTERVAL_SECONDS = 15 * 60
MAX_CURRENT_BYTES = 256 * 1024
CURRENT_FAILURE_SECONDS = 60


class CurrentUnavailable(ValueError):
    pass


def stable_event_id(ward_id: str, observed: datetime):
    return uuid5(
        NAMESPACE_URL,
        f"open-meteo:ward:{ward_id}:{observed.astimezone(UTC).isoformat()}",
    )


def make_observation(
    ward_id: str, observed: datetime, raw: dict, interval_seconds: int
) -> ObservationInput:
    rainfall = round(
        number(raw["precipitation"], 0, 1000) * 3600 / interval_seconds, 4
    )
    return ObservationInput(
        event_id=stable_event_id(ward_id, observed),
        ward_id=ward_id,
        temperature=number(raw["temperature_2m"], -60, 65),
        humidity=number(raw["relative_humidity_2m"], 0, 100),
        wind_speed=number(raw["wind_speed_10m"], 0, 500),
        rainfall=number(rainfall, 0, 1000),
        source="provider",
        observed_at=observed,
    )


def normalize_current(ward_id: str, payload: dict) -> ObservationInput:
    try:
        current, units = payload["current"], payload["current_units"]
        expected = {
            "temperature_2m": "°C",
            "wind_speed_10m": "km/h",
            "precipitation": "mm",
            "relative_humidity_2m": "%",
        }
        if any(units.get(key) != value for key, value in expected.items()):
            raise CurrentUnavailable("Unexpected current units")
        interval = current["interval"]
        if type(interval) is not int or interval <= 0:
            raise CurrentUnavailable("Invalid current interval")
        timestamp = current["time"]
        if type(timestamp) is not int:
            raise CurrentUnavailable("Invalid provider timestamp")
        observed = datetime.fromtimestamp(timestamp, UTC)
        return make_observation(ward_id, observed, current, interval)
    except CurrentUnavailable:
        raise
    except (AttributeError, KeyError, OverflowError, TypeError, ValueError) as exc:
        raise CurrentUnavailable("Invalid or unavailable current observation") from exc


def minute_bucket(value: datetime) -> int:
    return int(value.astimezone(UTC).timestamp()) // INTERVAL_SECONDS


class OpenMeteoCurrent:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        clock=None,
        max_pending=64,
    ):
        self.client = client
        self.clock = clock or (lambda: datetime.now(UTC))
        self.max_pending = max_pending
        self.inflight: dict[tuple[str, int], asyncio.Task] = {}
        self.cache: dict[tuple[str, int], WeatherEvent] = {}
        self.failures: dict[tuple[str, int], datetime] = {}
        self.slots = asyncio.Semaphore(4)

    def _now(self) -> datetime:
        return self.clock().astimezone(UTC)

    async def get_current(
        self, ward_id: str, latitude: float, longitude: float
    ) -> WeatherEvent:
        now = self._now()
        key = (ward_id, minute_bucket(now))
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        latest = await self._latest(ward_id)
        if latest is not None and minute_bucket(latest.observed_at) == key[1]:
            event = event_from_record(latest)
            self._remember(key, event, now)
            return event

        retry_at = self.failures.get(key)
        if retry_at is not None and retry_at > now:
            if latest is not None:
                return event_from_record(latest)
            raise CurrentUnavailable("Provider is cooling down")

        task = self.inflight.get(key)
        if task is not None and task.done():
            self.inflight.pop(key, None)
            task = None
        if task is None:
            if len(self.inflight) >= self.max_pending:
                if latest is not None:
                    return event_from_record(latest)
                raise CurrentUnavailable("Current queue is full")
            task = asyncio.create_task(
                self._load_current(ward_id, latitude, longitude)
            )
            self.inflight[key] = task
            task.add_done_callback(
                lambda done, request_key=key: self._finished(request_key, done)
            )
        try:
            event = await asyncio.shield(task)
        except CurrentUnavailable as exc:
            self.failures[key] = now + timedelta(seconds=CURRENT_FAILURE_SECONDS)
            if latest is not None:
                return event_from_record(latest)
            raise CurrentUnavailable("Provider current unavailable") from exc
        self._remember(key, event, now)
        return event

    async def _load_current(
        self, ward_id: str, latitude: float, longitude: float
    ) -> WeatherEvent:
        try:
            async with self.slots:
                payload = await fetch_json(
                    self.client,
                    {
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": WEATHER_VARIABLES,
                        "wind_speed_unit": "kmh",
                        "temperature_unit": "celsius",
                        "precipitation_unit": "mm",
                        "timeformat": "unixtime",
                        "timezone": "UTC",
                        "forecast_days": 1,
                    },
                    max_bytes=MAX_CURRENT_BYTES,
                    error_cls=CurrentUnavailable,
                )
            value = normalize_current(ward_id, payload)
            await ingest(value)
            record = await self._by_id(str(value.event_id))
            if record is None:
                raise CurrentUnavailable("Current observation was not stored")
            return event_from_record(record)
        except CurrentUnavailable:
            raise
        except Exception as exc:
            raise CurrentUnavailable("Provider current unavailable") from exc

    async def _latest(self, ward_id: str) -> Observation | None:
        async with Session() as session:
            return await session.scalar(
                select(Observation)
                .where(
                    Observation.ward_id == ward_id,
                    Observation.source == "provider",
                )
                .order_by(Observation.observed_at.desc(), Observation.id.desc())
                .limit(1)
            )

    async def _by_id(self, event_id: str) -> Observation | None:
        async with Session() as session:
            return await session.get(Observation, event_id)

    def _remember(
        self, key: tuple[str, int], event: WeatherEvent, now: datetime
    ) -> None:
        if len(self.cache) > 4096:
            for cache_key in tuple(self.cache):
                if cache_key[1] < key[1] - 1:
                    self.cache.pop(cache_key, None)
        self.cache[key] = event
        self.failures.pop(key, None)

    def _finished(self, key: tuple[str, int], task: asyncio.Task) -> None:
        if self.inflight.get(key) is task:
            self.inflight.pop(key, None)
        if not task.cancelled():
            task.exception()

    async def aclose(self):
        tasks = tuple(self.inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
