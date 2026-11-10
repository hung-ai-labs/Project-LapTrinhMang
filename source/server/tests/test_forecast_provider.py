import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from app.services.forecast import ForecastUnavailable, OpenMeteoForecast, next_hour, parse_hourly


@pytest.fixture
def hourly_payload():
    return {
        "hourly_units": {
            "time": "unixtime",
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "wind_speed_10m": "km/h",
            "precipitation": "mm",
        },
        "hourly": {
            "time": [int(datetime(2026, 11, 4, h, tzinfo=UTC).timestamp()) for h in (2, 3, 4)],
            "temperature_2m": [25, 29.1, 32],
            "relative_humidity_2m": [80, 79, 78],
            "wind_speed_10m": [10, 12.3, 15],
            "precipitation": [0, 0.2, 0.5],
        },
    }


def test_select_next_hour_and_preserve_precipitation_interval(hourly_payload):
    now = datetime(2026, 11, 4, 2, 20, tzinfo=UTC)
    target = next_hour(now)
    value = parse_hourly("001", hourly_payload, target, now)
    assert target == datetime(2026, 11, 4, 3, tzinfo=UTC)
    assert value.predicted_temperature == 29.1
    assert value.predicted_humidity == 79
    assert value.precipitation_mm == 0.2
    assert value.interval_seconds == 3600
    assert value.ward_id == "001"
    assert value.method == "open_meteo_hourly"
    assert next_hour(datetime(2026, 11, 4, 23, 20, tzinfo=UTC)).day == 5


@pytest.mark.parametrize("value", [None, True, float("nan"), float("inf"), -100])
def test_reject_invalid_forecast_values(hourly_payload, value):
    hourly_payload["hourly"]["temperature_2m"][1] = value
    with pytest.raises(ForecastUnavailable):
        parse_hourly(
            "001",
            hourly_payload,
            datetime(2026, 11, 4, 3, tzinfo=UTC),
            datetime(2026, 11, 4, 2, tzinfo=UTC),
        )


def test_missing_target_and_wrong_units_do_not_fall_back(hourly_payload):
    with pytest.raises(ForecastUnavailable):
        parse_hourly(
            "001",
            hourly_payload,
            datetime(2026, 11, 4, 8, tzinfo=UTC),
            datetime(2026, 11, 4, 2, tzinfo=UTC),
        )
    hourly_payload["hourly_units"]["precipitation"] = "mm/h"
    with pytest.raises(ForecastUnavailable):
        parse_hourly(
            "001",
            hourly_payload,
            datetime(2026, 11, 4, 3, tzinfo=UTC),
            datetime(2026, 11, 4, 2, tzinfo=UTC),
        )


def test_share_only_inflight_requests_and_fetch_fresh_for_later_preview(hourly_payload):
    calls = []
    now = datetime(2026, 11, 4, 2, 20, tzinfo=UTC)

    async def handler(request):
        calls.append(request)
        await asyncio.sleep(0.01)
        return httpx.Response(200, json=hourly_payload)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = OpenMeteoForecast(client, clock=lambda: now)
            try:
                assert calls == []
                values = await asyncio.gather(*[service.get("001", 21, 105) for _ in range(5)])
                assert all(value.predicted_temperature == 29.1 for value in values)
                assert len(calls) == 1
                assert calls[0].url.params["latitude"] == "21"
                assert "current" not in calls[0].url.params
                await service.get("001", 21, 105)
                assert len(calls) == 2
            finally:
                await service.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("status", [429, 500, 503])
def test_provider_http_failure_is_explicit(status):
    async def scenario():
        transport = httpx.MockTransport(lambda request: httpx.Response(status))
        async with httpx.AsyncClient(transport=transport) as client:
            service = OpenMeteoForecast(client)
            with pytest.raises(ForecastUnavailable):
                await service.get("001", 21, 105)
            await service.aclose()

    asyncio.run(scenario())


def test_provider_timeout_is_explicit():
    def handler(request):
        raise httpx.ReadTimeout("test timeout", request=request)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = OpenMeteoForecast(client)
            with pytest.raises(ForecastUnavailable):
                await service.get("001", 21, 105)
            await service.aclose()

    asyncio.run(scenario())


def test_concurrency_limit_and_bounded_queue(hourly_payload):
    async def scenario():
        gate = asyncio.Event()
        two_started = asyncio.Event()
        active, maximum = 0, 0

        async def handler(request):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            if active == 2:
                two_started.set()
            await gate.wait()
            active -= 1
            return httpx.Response(200, json=hourly_payload)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = OpenMeteoForecast(
                client,
                clock=lambda: datetime(2026, 11, 4, 2, 20, tzinfo=UTC),
                max_pending=3,
            )
            tasks = [asyncio.create_task(service.get(str(i), 21, 105)) for i in range(3)]
            while len(service.inflight) < 3:
                await asyncio.sleep(0)
            with pytest.raises(ForecastUnavailable, match="queue"):
                await service.get("extra", 21, 105)
            # Inflight registration happens before HTTP handlers actually start.
            await asyncio.wait_for(two_started.wait(), timeout=2)
            gate.set()
            await asyncio.gather(*tasks)
            assert maximum == 2
            await service.aclose()

    asyncio.run(scenario())


def test_cancelled_caller_does_not_cancel_shared_provider_request(hourly_payload):
    async def scenario():
        gate, started = asyncio.Event(), asyncio.Event()
        calls = 0

        async def handler(request):
            nonlocal calls
            calls += 1
            started.set()
            await gate.wait()
            return httpx.Response(200, json=hourly_payload)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = OpenMeteoForecast(client, clock=lambda: datetime(2026, 11, 4, 2, tzinfo=UTC))
            first = asyncio.create_task(service.get("001", 21, 105))
            await started.wait()
            second = asyncio.create_task(service.get("001", 21, 105))
            await asyncio.sleep(0)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            gate.set()
            assert (await second).predicted_temperature == 29.1
            assert calls == 1
            await service.aclose()

    asyncio.run(scenario())


def test_hour_boundary_during_fetch_requests_new_target(hourly_payload):
    async def scenario():
        now = datetime(2026, 11, 4, 2, 59, 59, tzinfo=UTC)
        calls = 0

        def handler(request):
            nonlocal now, calls
            calls += 1
            now = datetime(2026, 11, 4, 3, 0, 1, tzinfo=UTC)
            return httpx.Response(200, json=hourly_payload)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = OpenMeteoForecast(client, clock=lambda: now)
            result = await service.get("001", 21, 105)
            assert result.target_at.hour == 4
            assert result.predicted_temperature == 32
            assert calls == 2
            await service.aclose()

    asyncio.run(scenario())
