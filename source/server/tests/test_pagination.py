import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest

from app.db import Province, Ward, WeatherObservation
from app.db.session import Session, engine

LIST_PATHS = (
    "/api/v1/cities",
    "/api/v1/provinces",
    "/api/v1/provinces/01/wards",
    "/api/v1/weather/hanoi/history",
)


def seed_data():
    async def run():
        async with Session.begin() as session:
            session.add_all(
                [
                    Province(id="01", name="Tỉnh A", dataset_version="test"),
                    Province(id="02", name="Tỉnh B", dataset_version="test"),
                    Province(id="03", name="Tỉnh ẩn", dataset_version="test", is_active=False),
                ]
            )
            await session.flush()
            for code, province_id, name, active in (
                ("001", "01", "Phường trùng tên", True),
                ("002", "01", "Phường trùng tên", True),
                ("003", "01", "Xã A", True),
                ("004", "01", "Phường ẩn", False),
                ("005", "02", "Phường B", True),
            ):
                session.add(
                    Ward(
                        id=code,
                        province_id=province_id,
                        name=name,
                        dataset_version="test",
                        is_active=active,
                    )
                )
            start = datetime(2026, 10, 20, tzinfo=UTC)
            for number, city, minute in (
                (1, "hanoi", 0),
                (2, "hanoi", 1),
                (3, "hanoi", 1),
                (4, "danang", 2),
            ):
                session.add(
                    WeatherObservation(
                        id=str(UUID(int=number)),
                        legacy_city=city,
                        temperature=30,
                        humidity=70,
                        wind_speed=10,
                        rainfall=0,
                        source="simulator",
                        observed_at=start + timedelta(minutes=minute),
                    )
                )
        await engine.dispose()

    asyncio.run(run())


def test_cities_first_middle_last_and_out_of_range_pages(client):
    first = client.get("/api/v1/cities?limit=1").json()
    assert set(first) == {"count", "next", "previous", "results"}
    assert first["count"] == 3
    assert first["previous"] is None
    assert first["results"][0]["id"] == "hanoi"
    middle = client.get(first["next"]).json()
    assert middle["count"] == 3
    assert middle["results"][0]["id"] == "danang"
    assert client.get(middle["previous"]).json()["results"] == first["results"]
    last = client.get(middle["next"]).json()
    assert last["results"][0]["id"] == "hcm"
    assert last["next"] is None
    beyond = client.get("/api/v1/cities?limit=1&offset=3").json()
    assert beyond["count"] == 3
    assert beyond["results"] == []
    assert beyond["next"] is None
    assert client.get(beyond["previous"]).json()["results"] == last["results"]


def test_province_and_ward_pages_count_filtered_results_and_keep_filters(client):
    seed_data()
    first = client.get("/api/v1/provinces?q=Tỉnh&limit=1").json()
    assert first["count"] == 2
    assert first["results"][0]["id"] == "01"
    assert parse_qs(urlsplit(first["next"]).query)["q"] == ["Tỉnh"]
    assert client.get(first["next"]).json()["results"][0]["id"] == "02"
    filtered = client.get("/api/v1/provinces?q=Tỉnh A&limit=1").json()
    assert filtered["count"] == 1
    assert filtered["next"] is None

    first = client.get("/api/v1/provinces/01/wards?q=Phường&limit=1").json()
    assert first["count"] == 2
    assert first["results"][0]["id"] == "001"
    assert parse_qs(urlsplit(first["next"]).query)["q"] == ["Phường"]
    last = client.get(first["next"]).json()
    assert last["count"] == 2
    assert last["results"][0]["id"] == "002"
    assert last["next"] is None
    assert client.get(last["previous"]).json()["results"] == first["results"]


@pytest.mark.parametrize("path", LIST_PATHS)
def test_empty_pages_keep_envelope_and_count(client, path):
    seed_data()
    if path.endswith("history"):
        path = "/api/v1/weather/hcm/history"
    elif path.endswith("cities"):
        response = client.get(path + "?offset=5").json()
        assert response["count"] == 3
        assert response["results"] == []
        return
    response = client.get(path + "?q=Không có kết quả").json()
    assert response == {"count": 0, "next": None, "previous": None, "results": []}


@pytest.mark.parametrize("path", LIST_PATHS)
@pytest.mark.parametrize("query", ["limit=0", "limit=501", "offset=-1"])
def test_invalid_pagination_parameters_return_422(client, path, query):
    assert client.get(path + "?" + query).status_code == 422


def test_history_pages_keep_city_filter_order_and_single_record_endpoints(client):
    seed_data()
    first = client.get("/api/v1/weather/hanoi/history?limit=2").json()
    assert first["count"] == 3
    assert [row["id"] for row in first["results"]] == [str(UUID(int=3)), str(UUID(int=2))]
    last = client.get(first["next"]).json()
    assert last["count"] == 3
    assert [row["id"] for row in last["results"]] == [str(UUID(int=1))]
    assert last["next"] is None
    assert client.get(last["previous"]).json()["results"] == first["results"]
    current = client.get("/api/v1/weather/hanoi/current").json()
    forecast = client.get("/api/v1/weather/hanoi/forecast").json()
    assert current["observation"]["id"] == str(UUID(int=3))
    assert forecast["based_on"] == str(UUID(int=3))
    assert "results" not in current
    assert "results" not in forecast


def test_openapi_documents_model_tags_and_paginated_response_schemas(client):
    schema = client.get("/openapi.json").json()
    expected_tags = {
        "/api/v1/health": "Health",
        "/api/v1/cities": "City",
        "/api/v1/provinces": "Province",
        "/api/v1/provinces/{province_id}/wards": "Ward",
        "/api/v1/weather/{city}/history": "WeatherObservation",
        "/api/v1/weather/{city}/current": "WeatherObservation",
        "/api/v1/weather/{city}/forecast": "Forecast",
    }
    for path, tag in expected_tags.items():
        assert schema["paths"][path]["get"]["tags"] == [tag]
    assert schema["paths"]["/api/v1/geography/nearest-ward"]["post"]["tags"] == ["Ward"]
    for path in (
        "/api/v1/cities",
        "/api/v1/provinces",
        "/api/v1/provinces/{province_id}/wards",
        "/api/v1/weather/{city}/history",
    ):
        operation = schema["paths"][path]["get"]
        reference = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        response_schema = schema["components"]["schemas"][reference.rsplit("/", 1)[-1]]
        assert set(response_schema["properties"]) == {"count", "next", "previous", "results"}
        assert response_schema["properties"]["results"]["type"] == "array"
        assert {"limit", "offset"} <= {item["name"] for item in operation["parameters"]}
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
