from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings


def test_auth_lifecycle(client):
    value = {"name": " Đức ", "email": "DUC@example.com", "password": "StrongPass123!"}
    response = client.post("/api/v1/auth/register", json=value)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["user"]["name"] == "Đức"
    assert data["user"]["email"] == "duc@example.com"
    assert "password_hash" not in str(data)
    import asyncio

    from sqlalchemy import select

    from app.db import User
    from app.db.session import Session, engine

    async def check_hash():
        async with Session() as session:
            user = await session.scalar(select(User).where(User.email == "duc@example.com"))
            assert user.password_hash.startswith("$argon2id$")
            assert value["password"] not in user.password_hash
        await engine.dispose()

    asyncio.run(check_hash())
    assert client.post("/api/v1/auth/register", json=value).status_code == 409
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": value["email"], "password": "wrongpass"}
        ).status_code
        == 401
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": value["email"], "password": value["password"]}
    )
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["data"]["access_token"]}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer " + data["access_token"]}
        ).status_code
        == 401
    )


def test_invalid_tokens_and_inputs(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    expired = jwt.encode(
        {
            "sub": "missing",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
            "iss": "weather-stream",
            "aud": "weather-web",
            "ver": 0,
            "jti": "test",
        },
        get_settings().jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    for token in ["invalid", expired]:
        assert (
            client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token}).status_code
            == 401
        )
    for changes in [{"name": " "}, {"email": "invalid"}, {"password": "short"}]:
        assert (
            client.post(
                "/api/v1/auth/register",
                json={
                    "name": "Test",
                    "email": "test@example.com",
                    "password": "StrongPass123!",
                    **changes,
                },
            ).status_code
            == 422
        )
