from sqlalchemy.exc import OperationalError

from app.api import routes
from app.services import catalog as catalog_module
from app.services.catalog import CatalogCache


def break_database(monkeypatch, cache):
    async def failing_load(session):
        raise OperationalError("SELECT 1", {}, Exception("database is unreachable"))

    monkeypatch.setattr(cache, "_load", failing_load)


def test_catalog_is_served_from_the_cache_when_the_database_fails(
    client, public_data, monkeypatch,
):
    first = client.get("/api/v1/provinces")
    assert first.status_code == 200
    assert first.json()["data"]["count"] == 2
    assert "x-data-stale" not in first.headers

    cache = catalog_module.catalog_cache
    break_database(monkeypatch, cache)
    cache.loaded_at = 0.0

    stale = client.get("/api/v1/provinces")
    assert stale.status_code == 200
    assert stale.headers["x-data-stale"] == "true"
    assert stale.json()["data"]["count"] == 2

    wards = client.get("/api/v1/wards?province_id=01")
    assert wards.status_code == 200
    assert wards.headers["x-data-stale"] == "true"
    assert wards.json()["data"]["count"] == 3


def test_catalog_returns_503_without_a_cached_copy(client, monkeypatch):
    cache = catalog_module.catalog_cache
    break_database(monkeypatch, cache)

    response = client.get("/api/v1/provinces")
    assert response.status_code == 503
    assert "mất kết nối cơ sở dữ liệu" in response.json()["error"]["message"]


def test_wards_are_filtered_and_paginated(client, public_data):
    response = client.get("/api/v1/wards?province_id=02&page_size=1")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["count"] == 1
    assert body["results"][0]["province_id"] == "02"

    search = client.get("/api/v1/provinces?q=Tỉnh A")
    assert search.json()["data"]["count"] == 1


def test_websocket_is_accepted_while_the_database_is_unreachable(client, public_data, monkeypatch):
    async def failing_lookup(session, ward_id):
        raise OperationalError("SELECT 1", {}, Exception("database is unreachable"))

    monkeypatch.setattr(routes, "active_ward", failing_lookup)

    with client.websocket_connect("/api/v1/ws/wards/001/weather") as socket:
        socket.send_text("ping")


def test_catalog_cache_keeps_the_last_copy_when_a_refresh_fails():
    cache = CatalogCache()
    cache.provinces = []
    cache.loaded_at = 0.0
    assert cache._fresh(0.0) is False
    cache.loaded_at = 1.0
    assert cache._fresh(1.0) is False
