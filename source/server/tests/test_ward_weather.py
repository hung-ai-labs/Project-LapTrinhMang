import asyncio
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import select, update
from test_stream import observation, send

from app.db import Observation, Ward
from app.db.session import Session, engine
from app.main import app
from app.services.forecast import ForecastUnavailable


def snapshot():
    async def run():
        async with Session() as session:
            rows = (
                await session.execute(select(Observation.__table__).order_by(Observation.id))
            ).all()
        await engine.dispose()
        return [tuple(row) for row in rows]

    return asyncio.run(run())


def test_preview_is_read_only_and_independent_of_current(public_data, client):
    before = snapshot()
    assert client.get("/api/v1/wards/003/weather/current").status_code == 404
    response = client.get("/api/v1/wards/003/weather/forecast")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["data"]["predicted_temperature"] == 31.5
    assert snapshot() == before
    assert client.get("/api/v1/wards/003/weather/current").status_code == 404
    assert client.get("/api/v1/wards/003/weather/history").json()["data"]["results"] == []


def test_preview_failure_does_not_change_current_history(public_data, client, monkeypatch):
    before = snapshot()

    async def failure(*args):
        raise ForecastUnavailable("test")

    monkeypatch.setattr(app.state.forecast_service, "get", failure)
    assert client.get("/api/v1/wards/001/weather/forecast").status_code == 503
    assert client.get("/api/v1/wards/001/weather/current").status_code == 200
    assert client.get("/api/v1/wards/001/weather/history").json()["data"]["count"] == 3
    assert snapshot() == before


def test_unknown_inactive_and_missing_coordinate_wards(public_data, client):
    for ward in ("missing", "004", "006"):
        assert client.get(f"/api/v1/wards/{ward}/weather/forecast").status_code == 404
        assert client.get(f"/api/v1/wards/{ward}/weather/history").status_code == 404
        assert send(observation(ward_id=ward))["code"] == "invalid_ward"

    async def remove_coordinates():
        async with Session.begin() as session:
            await session.execute(
                update(Ward)
                .where(Ward.id == "003")
                .values(
                    latitude=None,
                    longitude=None,
                )
            )
        await engine.dispose()

    asyncio.run(remove_coordinates())
    assert client.get("/api/v1/wards/003/weather/forecast").status_code == 422


def test_old_city_and_forecast_frames_are_rejected(ward_catalog, client):
    old = observation(city="hanoi")
    old.pop("ward_id")
    assert send(old)["code"] == "invalid_observation"
    assert (
        send({"ward_id": "001", "predicted_temperature": 32, "target_at": "2026-11-04T03:00:00Z"})[
            "code"
        ]
        == "invalid_observation"
    )
    assert snapshot() == []


def test_duplicate_conflict_retains_first_snapshot(ward_catalog, client):
    value = observation()
    assert send(value)["status"] == "accepted"
    assert send(value)["status"] == "duplicate"
    reply = send({**value, "temperature": value["temperature"] + 1})
    assert reply["code"] == "event_conflict"
    assert reply["event_id"] == value["event_id"]
    current = client.get("/api/v1/wards/001/weather/current").json()["data"]
    assert current["observation"]["temperature"] == value["temperature"]
    assert len(snapshot()) == 1


def test_api_remains_available_while_two_producers_send(ward_catalog, client):
    def produce():
        for _ in range(20):
            assert send(observation(event_id=str(uuid4())))["status"] == "accepted"

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(produce) for _ in range(2)]
        for _ in range(10):
            assert client.get("/api/v1/health").status_code == 200
        for job in jobs:
            job.result(timeout=20)
    assert len(snapshot()) == 40
