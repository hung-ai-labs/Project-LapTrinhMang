def register(client, email):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "User kiểm thử",
            "email": email,
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    assert response.json()["success"] is True
    assert response.headers["cache-control"] == "no-store"
    token = response.json()["data"]["access_token"]
    return {"Authorization": "Bearer " + token}


def test_address_is_optional_and_scoped_to_the_authenticated_user(public_data, client):
    first = register(client, "first@example.com")
    second = register(client, "second@example.com")
    url = "/api/v1/users/me/address"
    assert client.get(url, headers=first).json()["data"] == {
        "address_text": None,
        "ward": None,
        "province": None,
    }
    saved = client.patch(
        url,
        headers=first,
        json={
            "ward_id": "001",
            "address_text": "  Địa chỉ riêng A  ",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["address_text"] == "Địa chỉ riêng A"
    assert saved.json()["data"]["ward"]["id"] == "001"
    assert saved.json()["data"]["province"]["id"] == "01"
    assert client.get(url, headers=second).json()["data"]["ward"] is None
    assert (
        client.patch(
            url,
            headers=first,
            json={
                "ward_id": "002",
                "user_id": "another-user",
            },
        ).status_code
        == 422
    )
    assert client.get(url, headers=first).json()["data"]["ward"]["id"] == "001"
    assert client.patch(url, headers=second, json={"ward_id": "002"}).status_code == 200
    assert client.get(url, headers=first).json()["data"]["ward"]["id"] == "001"
    assert client.get(url, headers=second).json()["data"]["ward"]["id"] == "002"
    removed = client.delete(url, headers=first)
    assert removed.status_code == 200
    assert removed.json() == {
        "success": True,
        "data": {"address_text": None, "ward": None, "province": None},
    }
    assert client.get(url, headers=second).json()["data"]["ward"]["id"] == "002"
    assert client.get("/api/v1/wards/001").status_code == 200
    assert client.post("/api/v1/auth/logout", headers=first).json() == {
        "success": True,
        "data": None,
    }
    assert client.get(url, headers=first).status_code == 401
    assert client.get(url, headers=second).status_code == 200


def test_address_requires_identity_but_public_content_does_not(public_data, client):
    url = "/api/v1/users/me/address"
    for response in (
        client.get(url),
        client.patch(url, json={"ward_id": "001"}),
        client.delete(url),
    ):
        assert response.status_code == 401
        assert response.json()["success"] is False
        assert response.headers["www-authenticate"] == "Bearer"
    assert client.get("/api/v1/provinces").status_code == 200
    assert client.get("/api/v1/weather/hanoi/current").status_code == 200


def test_invalid_or_inactive_wards_do_not_replace_a_saved_address(public_data, client):
    headers = register(client, "person@example.com")
    url = "/api/v1/users/me/address"
    client.patch(url, headers=headers, json={"ward_id": "001", "address_text": "Địa chỉ A"})
    for ward_id in ("004", "006", "missing"):
        response = client.patch(url, headers=headers, json={"ward_id": ward_id})
        assert response.status_code == 404
        assert response.json()["success"] is False
    assert client.get(url, headers=headers).json()["data"]["address_text"] == "Địa chỉ A"
    assert (
        client.patch(
            url,
            headers=headers,
            json={
                "ward_id": "001",
                "address_text": "a" * 501,
            },
        ).status_code
        == 422
    )


def test_cors_allows_browser_address_updates(client):
    response = client.options(
        "/api/v1/users/me/address",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "PATCH" in response.headers["access-control-allow-methods"]
    assert "DELETE" in response.headers["access-control-allow-methods"]
