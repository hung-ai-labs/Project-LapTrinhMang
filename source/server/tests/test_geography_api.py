import asyncio
import json
import sqlite3

from app.db.session import Session, engine
from app.services.administrative_units import AdministrativeSnapshot, apply_snapshot


def seed_catalog():
    snapshot = AdministrativeSnapshot.model_validate(
        {
            "dataset_version": "test",
            "provinces": [{"id": "01", "name": "Tỉnh kiểm thử"}],
            "wards": [
                {
                    "id": "00001",
                    "province_id": "01",
                    "name": "Phường A",
                    "latitude": "21.001",
                    "longitude": "105",
                },
                {
                    "id": "00002",
                    "province_id": "01",
                    "name": "Phường B",
                    "latitude": "22",
                    "longitude": "105",
                },
            ],
        }
    )

    async def run():
        async with Session.begin() as session:
            await apply_snapshot(session, snapshot)
        await engine.dispose()

    asyncio.run(run())


def test_nearest_endpoint_and_catalog_queries(client):
    seed_catalog()
    assert client.get("/api/v1/provinces").json() == {
        "count": 1, "next": None, "previous": None,
        "results": [{"id": "01", "name": "Tỉnh kiểm thử"}],
    }
    wards = client.get("/api/v1/provinces/01/wards?q=Phường&limit=1&offset=1").json()
    assert wards["count"] == 2
    assert [row["id"] for row in wards["results"]] == ["00002"]
    response = client.post(
        "/api/v1/geography/nearest-ward", json={"latitude": 21, "longitude": 105}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["ward_id"] == "00001"
    assert result["province_id"] == "01"
    assert result["match_type"] == "nearest"
    assert 0 < result["distance_km"] < 1
    with sqlite3.connect(engine.url.database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0


def test_empty_and_invalid_geography_requests(client):
    assert (
        client.post(
            "/api/v1/geography/nearest-ward", json={"latitude": 21, "longitude": 105}
        ).status_code
        == 404
    )
    assert client.get("/api/v1/provinces/missing/wards").status_code == 404
    assert (
        client.post(
            "/api/v1/geography/nearest-ward", json={"latitude": 91, "longitude": 105}
        ).status_code
        == 422
    )
    assert client.post("/api/v1/geography/nearest-ward", json={"latitude": 21}).status_code == 422
    assert (
        client.post(
            "/api/v1/geography/nearest-ward",
            content=json.dumps({"latitude": "NaN", "longitude": 105}),
            headers={"content-type": "application/json"},
        ).status_code
        == 422
    )
