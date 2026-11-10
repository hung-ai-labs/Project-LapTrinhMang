from datetime import UTC, datetime

import httpx
import pytest

from app.services import provider_forecast as service


def payload():
    t = int(datetime(2026, 11, 3, 17, tzinfo=UTC).timestamp())
    return {
        "hourly": {
            "time": [t],
            "temperature_2m": [25],
            "relative_humidity_2m": [80],
            "wind_speed_10m": [10],
            "precipitation": [2],
            "precipitation_probability": [70],
        },
        "hourly_units": {
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "wind_speed_10m": "km/h",
            "precipitation": "mm",
            "precipitation_probability": "%",
        },
        "daily": {
            "time": [t],
            "temperature_2m_min": [20],
            "temperature_2m_max": [28],
            "precipitation_sum": [10],
            "precipitation_probability_max": [85],
            "wind_speed_10m_max": [15],
        },
        "daily_units": {
            "temperature_2m_min": "°C",
            "temperature_2m_max": "°C",
            "precipitation_sum": "mm",
            "precipitation_probability_max": "%",
            "wind_speed_10m_max": "km/h",
        },
    }


def test_parse_timezone_units_and_nulls():
    raw = payload()
    raw["hourly"]["precipitation_probability"] = [None]
    result = service.parse_forecast("hanoi", raw)
    assert result.daily[0].date.isoformat() == "2026-11-04"
    assert result.hourly[0].precipitation == 2
    assert result.daily[0].precipitation_sum == 10
    assert result.hourly[0].rain_probability is None
    assert result.is_project_ai is False
    raw["hourly_units"]["wind_speed_10m"] = "mph"
    with pytest.raises(ValueError):
        service.parse_forecast("hanoi", raw)
    raw = payload()
    raw["daily"]["temperature_2m_min"] = []
    with pytest.raises(ValueError):
        service.parse_forecast("hanoi", raw)


def test_public_endpoint_cache_and_validation(client, monkeypatch):
    service._cache.clear()
    calls = []

    async def fetch(city, days):
        calls.append((city, days))
        return service.parse_forecast(city, payload())

    monkeypatch.setattr(service, "fetch_forecast", fetch)
    url = "/api/v1/weather/hanoi/provider-forecast?days=7"
    for _ in range(2):
        response = client.get(url)
        assert response.status_code == 200
        assert response.json()["data"]["source"] == "open-meteo"
    assert calls == [("hanoi", 7)]
    assert client.get(url.replace("hanoi", "danang")).status_code == 200
    assert client.get(url.replace("days=7", "days=16")).status_code == 200
    assert len(calls) == 3
    assert client.get(url.replace("days=7", "days=17")).status_code == 422
    assert client.get(url.replace("hanoi", "unknown")).status_code == 422
    service._cache.clear()


def test_provider_failure_does_not_fake_forecast(client, monkeypatch):
    service._cache.clear()

    async def unavailable(city, days):
        raise httpx.ReadTimeout("test")

    monkeypatch.setattr(service, "fetch_forecast", unavailable)
    response = client.get("/api/v1/weather/hanoi/provider-forecast")
    assert response.status_code == 502
    assert response.json()["success"] is False
    assert not service._cache
