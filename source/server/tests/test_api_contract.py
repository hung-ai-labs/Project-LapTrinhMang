import asyncio
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import get_settings
from app.db.session import get_session
from app.main import app

LIST_PATHS = ("/provinces", "/wards", "/wards/001/weather/history")
PUBLIC_PATHS = (
    "/health",
    "/provinces",
    "/provinces/01",
    "/wards",
    "/wards/001",
    "/wards/001/weather/current",
    "/wards/001/weather/history",
    "/wards/001/weather/forecast",
)


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
def test_all_content_apis_are_public_and_success_wrapped(public_data, client, headers):
    for path in PUBLIC_PATHS:
        response = client.get("/api/v1" + path, headers=headers)
        assert response.status_code == 200, path
        assert set(response.json()) == {"success", "data"}
        assert response.json()["success"] is True
    nearest = client.post(
        "/api/v1/geography/nearest-ward",
        json={"latitude": 21, "longitude": 105},
        headers=headers,
    )
    assert nearest.status_code == 200
    assert nearest.json()["data"]["ward"]["id"] == "001"
    assert nearest.json()["data"]["province"]["id"] == "01"


def test_public_content_does_not_require_a_configured_jwt_secret(public_data, client, monkeypatch):
    monkeypatch.setattr(get_settings(), "jwt_secret", SecretStr(""))
    for path in PUBLIC_PATHS:
        assert client.get("/api/v1" + path).status_code == 200
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "person@example.com",
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 503
    assert response.json()["success"] is False


def test_page_links_are_absolute_and_first_last_pages_have_expected_shape(public_data, client):
    first = client.get("https://weather.example/api/v1/provinces?page_size=1").json()
    assert first["success"] is True
    page = first["data"]
    assert set(page) == {"count", "next", "previous", "results"}
    assert page["count"] == 2
    assert page["previous"] is None
    assert page["results"][0]["id"] == "01"
    assert page["next"].startswith("https://weather.example/api/v1/provinces?")
    assert parse_qs(urlsplit(page["next"]).query) == {"page": ["2"], "page_size": ["1"]}
    last = client.get(page["next"]).json()["data"]
    assert last["results"][0]["id"] == "02"
    assert client.get(last["previous"]).json()["data"]["results"] == page["results"]
    assert last["next"] is None
    assert client.get("/api/v1/provinces?page=3&page_size=1").status_code == 404


def test_catalog_count_and_links_keep_search_and_province_filters(public_data, client):
    first = client.get("/api/v1/provinces?q=Tỉnh&page_size=1").json()["data"]
    assert first["count"] == 2
    assert first["results"][0]["id"] == "01"
    assert client.get(first["next"]).json()["data"]["results"][0]["id"] == "02"
    page = client.get("/api/v1/wards?province_id=01&q=Phường&page_size=1").json()["data"]
    assert page["count"] == 2
    assert page["results"][0]["id"] == "001"
    query = parse_qs(urlsplit(page["next"]).query)
    assert query["province_id"] == ["01"]
    assert query["q"] == ["Phường"]
    last = client.get(page["next"]).json()["data"]
    assert last["count"] == 2
    assert last["results"][0]["id"] == "002"
    assert last["next"] is None
    assert client.get(last["previous"]).json()["data"]["results"] == page["results"]
    assert client.get("/api/v1/wards/004").status_code == 404
    assert client.get("/api/v1/wards/006").status_code == 404


def test_history_pagination_keeps_ward_source_and_stable_time_order(public_data, client):
    first = client.get("/api/v1/wards/001/weather/history?page_size=2").json()["data"]
    assert first["count"] == 3
    assert [row["id"] for row in first["results"]] == [str(UUID(int=3)), str(UUID(int=2))]
    last = client.get(first["next"]).json()["data"]
    assert [row["id"] for row in last["results"]] == [str(UUID(int=1))]
    assert last["next"] is None
    current = client.get("/api/v1/wards/001/weather/current").json()["data"]
    forecast = client.get("/api/v1/wards/001/weather/forecast").json()["data"]
    assert current["observation"]["id"] == str(UUID(int=3))
    assert forecast["ward_id"] == "001"
    assert forecast["method"] == "open_meteo_hourly"
    assert "results" not in current and "results" not in forecast


@pytest.mark.parametrize("path", ["/provinces", "/wards"])
def test_empty_lists_are_wrapped_pages(client, path):
    response = client.get("/api/v1" + path)
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {"count": 0, "next": None, "previous": None, "results": []},
    }


@pytest.mark.parametrize("path", LIST_PATHS)
@pytest.mark.parametrize("query", ["page=0", "page_size=0", "page_size=101"])
def test_invalid_pages_return_standard_validation_error(client, path, query):
    response = client.get("/api/v1" + path + "?" + query)
    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["data"] is None
    assert response.json()["error"]["code"] == "validation_error"


def test_not_found_and_validation_errors_do_not_echo_input_secrets(client):
    missing = client.get("/api/v1/not-found")
    assert missing.status_code == 404
    assert missing.json()["success"] is False
    invalid = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Person",
            "email": "person@example.com",
            "password": "secret",
        },
    )
    assert invalid.status_code == 422
    assert "secret" not in invalid.text
    assert invalid.json()["error"]["details"][0]["loc"] == ["body", "password"]
    nan = client.post(
        "/api/v1/geography/nearest-ward",
        content='{"latitude":NaN,"longitude":105}',
        headers={"content-type": "application/json"},
    )
    assert nan.status_code == 422
    assert nan.json()["success"] is False


def test_unexpected_errors_use_standard_envelope_without_internal_details():
    async def failure():
        raise RuntimeError("private-test-detail")

    async def scenario():
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/provinces")
            assert response.status_code == 500
            assert response.json()["error"]["code"] == "internal_error"
            assert response.json()["success"] is False
            assert "private-test-detail" not in response.text

    app.dependency_overrides[get_session] = failure
    try:
        asyncio.run(scenario())
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_docs_group_models_describe_envelopes_and_keep_public_apis_anonymous(client):
    schema = client.get("/openapi.json").json()
    assert "openapi" in schema and "success" not in schema
    for url in ("/docs", "/redoc"):
        assert client.get(url).status_code == 200
    for path in PUBLIC_PATHS:
        template = path.replace("/provinces/01", "/provinces/{province_id}")
        template = template.replace("/wards/001", "/wards/{ward_id}")
        template = template.replace("/wards/001/weather/", "/weather/{city}/")
        operation = schema["paths"]["/api/v1" + template]["get"]
        assert not operation.get("security")
        assert len(operation["tags"]) == 1
    assert schema["paths"]["/api/v1/users/me/address"]["get"]["security"]
    assert schema["paths"]["/api/v1/auth/me"]["get"]["security"]
    for path in ("/api/v1/provinces", "/api/v1/wards"):
        operation = schema["paths"][path]["get"]
        assert {"page", "page_size"} <= {item["name"] for item in operation["parameters"]}
        reference = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        wrapper = schema["components"]["schemas"][reference.rsplit("/", 1)[-1]]
        assert set(wrapper["properties"]) == {"success", "data"}
        data_ref = wrapper["properties"]["data"]["$ref"]
        page = schema["components"]["schemas"][data_ref.rsplit("/", 1)[-1]]
        assert set(page["properties"]) == {"count", "next", "previous", "results"}
        error_ref = operation["responses"]["422"]["content"]["application/json"]["schema"]["$ref"]
        error = schema["components"]["schemas"][error_ref.rsplit("/", 1)[-1]]
        assert set(error["properties"]) == {"success", "data", "error"}


def test_removed_city_catalog_is_not_in_routes_or_openapi(client):
    response = client.get("/api/v1/cities")
    assert response.status_code == 404
    assert response.json()["success"] is False
    schema = client.get("/openapi.json").json()
    assert "/api/v1/cities" not in schema["paths"]
    assert "City" not in {tag["name"] for tag in schema["tags"]}
    assert "CitiesOut" not in schema["components"]["schemas"]



def test_empty_ward_history_is_a_wrapped_page(ward_catalog, client):
    response = client.get("/api/v1/wards/003/weather/history")
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {"count": 0, "next": None, "previous": None, "results": []},
    }
