import asyncio
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from pwdlib import PasswordHash
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import Base
from app.db.session import get_session
from app.main import app

SERVER_DIRECTORY = Path(__file__).resolve().parents[1]


def run_command(database, *arguments, check=True):
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{database}"
    result = subprocess.run(
        [sys.executable, *arguments],
        cwd=SERVER_DIRECTORY,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def migrate(database, *arguments, check=True):
    return run_command(database, "-m", "alembic", *arguments, check=check)


def test_migration_chain_has_one_new_revision():
    directory = ScriptDirectory.from_config(Config(str(SERVER_DIRECTORY / "alembic.ini")))
    assert directory.get_heads() == ["0003"]
    assert directory.get_revision("0003").down_revision == "0002"
    assert directory.get_revision("0002").down_revision == "0001"


def test_upgrade_preserves_main_data_matches_models_and_keeps_jwt_working(tmp_path, client):
    database = tmp_path / "migration.db"
    migrate(database, "upgrade", "0002")
    user_id, event_id = str(uuid4()), str(uuid4())
    password_hash = PasswordHash.recommended().hash("StrongPass123!")
    user_before = (
        user_id,
        "User từ main",
        "existing@example.com",
        password_hash,
        4,
        "2020-01-01 00:00:00",
    )
    observation_before = (
        event_id,
        "hanoi",
        30.0,
        70.0,
        10.0,
        0.0,
        "simulator",
        "2026-10-20 00:00:00",
    )
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", user_before)
        connection.execute(
            "INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?)", observation_before
        )
    migrate(database, "upgrade", "head")
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute(
                "SELECT id, name, email, password_hash, token_version, created_at FROM users"
            ).fetchone()
            == user_before
        )
        assert (
            connection.execute(
                "SELECT id, city, temperature, humidity, wind_speed, rainfall, source, observed_at "
                "FROM observations"
            ).fetchone()
            == observation_before
        )
        assert connection.execute("SELECT updated_at FROM users").fetchone()[0] == user_before[-1]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    engine = create_engine(f"sqlite:///{database}")
    try:
        with engine.connect() as connection:
            assert (
                compare_metadata(
                    MigrationContext.configure(connection, opts={"compare_server_default": True}),
                    Base.metadata,
                )
                == []
            )
    finally:
        engine.dispose()

    auth_engine = create_async_engine(f"sqlite+aiosqlite:///{database}", poolclass=NullPool)
    factory = async_sessionmaker(auth_engine, expire_on_commit=False)

    async def migrated_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = migrated_session
    try:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "existing@example.com",
                "password": "StrongPass123!",
            },
        )
        assert response.status_code == 200
        assert response.json()["data"]["user"] == {
            "id": user_id,
            "name": "User từ main",
            "email": "existing@example.com",
        }
        headers = {"Authorization": "Bearer " + response.json()["data"]["access_token"]}
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    finally:
        app.dependency_overrides.pop(get_session, None)
        asyncio.run(auth_engine.dispose())


def test_import_cli_is_read_only_by_default_and_idempotent_when_applied(tmp_path):
    database = tmp_path / "catalog.db"
    command = "../scripts/import_administrative_units.py"
    result = run_command(database, command)
    assert json.loads(result.stdout)["mode"] == "dry_run"
    assert not database.exists()
    migrate(database, "upgrade", "head")
    for _ in range(2):
        result = run_command(database, command, "--apply")
        report = json.loads(result.stdout)
        assert report["provinces"] == 34
        assert report["wards"] == 3321
        assert report["wards_with_coordinates"] == 3321
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM provinces").fetchone()[0] == 34
        assert connection.execute("SELECT COUNT(*) FROM wards").fetchone()[0] == 3321
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert (
            connection.execute("SELECT province_id FROM wards WHERE id='00004'").fetchone()[0]
            == "01"
        )


def test_downgrade_preserves_main_accounts(tmp_path):
    database = tmp_path / "downgrade.db"
    migrate(database, "upgrade", "0002")
    record = (str(uuid4()), "Tên từ main", "old@example.com", "test-only", 3, "2020-01-01 00:00:00")
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", record)
    migrate(database, "upgrade", "head")
    migrate(database, "downgrade", "0002")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT * FROM users").fetchone() == record
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002"


@pytest.mark.parametrize("saved_location", [False, True])
def test_downgrade_does_not_drop_catalog_or_saved_locations(tmp_path, saved_location):
    database = tmp_path / "protected.db"
    migrate(database, "upgrade", "head")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO provinces (id, name, dataset_version, is_active) "
            "VALUES ('01', 'Tỉnh kiểm thử', 'test', 1)"
        )
        connection.execute(
            "INSERT INTO wards (id, province_id, name, dataset_version, is_active) "
            "VALUES ('00001', '01', 'Xã kiểm thử', 'test', 1)"
        )
        if saved_location:
            connection.execute(
                "INSERT INTO users (id, name, email, password_hash, default_ward_id) "
                "VALUES (?, 'User kiểm thử', 'saved@example.com', 'test-only', '00001')",
                (str(uuid4()),),
            )
    result = migrate(database, "downgrade", "0002", check=False)
    assert result.returncode != 0
    assert "preserved before downgrading" in result.stderr
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM wards").fetchone()[0] == 1
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0003"
