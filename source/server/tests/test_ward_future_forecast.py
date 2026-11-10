import asyncio
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import select, update

from app.db import Observation, Ward
from app.db.session import Session, engine
from app.main import app
from app.schemas.weather import FutureForecastOut, FutureHourOut
from app.services import ward_future_forecast as service
from app.services.forecast import next_hour

START = datetime(2026, 11, 9, 17, tzinfo=UTC)
NOW = datetime(2026, 11, 10, 14, 15, tzinfo=UTC)


def payload(count=192):
    times = [int((START + timedelta(hours=index)).timestamp()) for index in range(count)]
    return {
        "hourly": {
            "time": times,
            "temperature_2m": [25.0] * count,
            "relative_humidity_2m": [80.0] * count,
            "precipitation": [0.5] * count,
            "rain": [0.2] * count,
            "precipitation_probability": [70] * count,
            "showers": [0.3] * count,
            "weather_code": [51] * count,
            "wind_speed_10m": [10.0] * count,
        },
        "hourly_units": {
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "precipitation": "mm",
            "rain": "mm",
            "precipitation_probability": "%",
            "showers": "mm",
            "weather_code": "wmo code",
            "wind_speed_10m": "km/h",
        },
    }


def test_parse_future_forecast_filters_and_maps():
    result = service.parse_future_forecast("00004", "Ba Đình", "01", payload(), NOW)
    vietnam = ZoneInfo("Asia/Ho_Chi_Minh")
    first = datetime(2026, 11, 10, 22, tzinfo=vietnam)
    assert result.ward_id == "00004"
    assert result.ward_name == "Ba Đình"
    assert result.province_id == "01"
    assert result.days == 7
    assert result.hours == 168
    assert result.hourly[0].time == first
    assert result.hourly[-1].time == first + timedelta(hours=167)
    assert result.hourly[0].temperature == 25.0
    assert result.hourly[0].humidity == 80.0
    assert result.hourly[0].wind_speed == 10.0
    assert result.hourly[0].rainfall == 0.5
    assert result.hourly[0].rain_probability == 70.0
    assert result.hourly[0].rain == 0.2
    assert result.hourly[0].showers == 0.3
    assert result.hourly[0].weather_code == 51
    assert result.retrieved_at == NOW.astimezone(vietnam)
    assert result.units.rainfall == "mm/giờ"


def test_parse_future_forecast_allows_nulls_and_rejects_bad_values():
    raw = payload()
    raw["hourly"]["temperature_2m"][22] = None
    result = service.parse_future_forecast("00004", "Ba Đình", "01", raw, NOW)
    assert result.hourly[0].temperature is None

    raw = payload()
    raw["hourly_units"]["wind_speed_10m"] = "mph"
    with pytest.raises(service.FutureForecastUnavailable):
        service.parse_future_forecast("00004", "Ba Đình", "01", raw, NOW)

    raw = payload()
    raw["hourly"]["weather_code"][22] = True
    with pytest.raises(service.FutureForecastUnavailable):
        service.parse_future_forecast("00004", "Ba Đình", "01", raw, NOW)


def test_future_service_uses_hourly_params_and_cache():
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload())

    async def scenario():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            forecast = service.OpenMeteoWardFuture(client, clock=lambda: NOW)
            first = await forecast.get("00004", "Ba Đình", "01", 21.0, 105.0)
            second = await forecast.get("00004", "Ba Đình", "01", 21.0, 105.0)
            assert first == second
            assert len(calls) == 1
            params = calls[0].url.params
            assert params["forecast_days"] == "8"
            assert params["timeformat"] == "unixtime"
            assert params["timezone"] == "Asia/Ho_Chi_Minh"
            assert "weather_code" in params["hourly"]
            assert "showers" in params["hourly"]

    asyncio.run(scenario())


def test_public_future_endpoint_shape_and_no_store(public_data, client, monkeypatch):
    now = datetime.now(UTC)
    vietnam = ZoneInfo("Asia/Ho_Chi_Minh")
    value = FutureForecastOut(
        ward_id="001",
        ward_name="Phường trùng tên",
        province_id="01",
        retrieved_at=now.astimezone(vietnam),
        hours=1,
        hourly=[
            FutureHourOut(
                time=next_hour(now).astimezone(vietnam),
                temperature=31.5,
                humidity=79.0,
                wind_speed=12.3,
                rainfall=0.2,
                rain_probability=70.0,
                rain=0.1,
                showers=0.1,
                weather_code=51,
            )
        ],
    )

    async def get(*args):
        return value

    monkeypatch.setattr(app.state.future_forecast_service, "get", get)
    response = client.get("/api/v1/wards/001/weather/future")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["ward_id"] == "001"
    assert data["ward_name"] == "Phường trùng tên"
    assert data["province_id"] == "01"
    assert data["source"] == "open-meteo"
    assert data["data_kind"] == "model_forecast"
    assert data["is_project_ai"] is False
    assert data["days"] == 7
    assert data["hours"] == 1
    assert data["interval_seconds"] == 3600
    assert data["units"]["rainfall"] == "mm/giờ"
    assert data["hourly"][0]["rainfall"] == 0.2
    assert data["hourly"][0]["rain_probability"] == 70.0
    assert data["hourly"][0]["time"].endswith("+07:00")
    assert data["retrieved_at"].endswith("+07:00")


def test_future_endpoint_errors(public_data, client, monkeypatch):
    for ward in ("missing", "004", "006"):
        assert client.get(f"/api/v1/wards/{ward}/weather/future").status_code == 404

    async def remove_coordinates():
        async with Session.begin() as session:
            await session.execute(
                update(Ward)
                .where(Ward.id == "003")
                .values(latitude=None, longitude=None)
            )
        await engine.dispose()

    asyncio.run(remove_coordinates())
    assert client.get("/api/v1/wards/003/weather/future").status_code == 422

    async def unavailable(*args):
        raise service.FutureForecastUnavailable("test")

    monkeypatch.setattr(app.state.future_forecast_service, "get", unavailable)
    response = client.get("/api/v1/wards/001/weather/future")
    assert response.status_code == 503
    assert response.json()["success"] is False


def test_future_endpoint_does_not_write_observations(public_data, client, monkeypatch):
    async def snapshot():
        async with Session() as session:
            rows = (
                await session.execute(select(Observation.__table__).order_by(Observation.id))
            ).all()
        await engine.dispose()
        return [tuple(row) for row in rows]

    before = asyncio.run(snapshot())
    value = FutureForecastOut(
        ward_id="001",
        ward_name="Phường trùng tên",
        province_id="01",
        retrieved_at=datetime.now(UTC),
        hours=0,
        hourly=[],
    )

    async def get(*args):
        return value

    monkeypatch.setattr(app.state.future_forecast_service, "get", get)
    assert client.get("/api/v1/wards/001/weather/future").status_code == 200
    assert asyncio.run(snapshot()) == before
