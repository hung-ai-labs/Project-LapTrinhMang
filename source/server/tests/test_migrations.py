import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db import Base

SERVER_DIRECTORY = Path(__file__).resolve().parents[1]


def migrate(database, *arguments, check=True):
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{database}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=SERVER_DIRECTORY,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def insert_legacy(database, humidity=80):
    record = (str(uuid4()), "hanoi", 36.0, humidity, 55.0, 25.0, "simulator", "2026-10-20 05:00:00")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO observations "
            "(id, city, temperature, humidity, wind_speed, rainfall, source, observed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            record,
        )
    return record


def test_upgrade_preserves_legacy_rows_matches_models_and_safe_downgrade(tmp_path):
    database = tmp_path / "migration.db"
    migrate(database, "upgrade", "0001")
    before = insert_legacy(database)
    migrate(database, "upgrade", "head")
    with sqlite3.connect(database) as connection:
        after = connection.execute(
            "SELECT id, city, temperature, humidity, wind_speed, rainfall, source, observed_at "
            "FROM observations"
        ).fetchone()
        assert after == before
        assert connection.execute("SELECT ward_id FROM observations").fetchone()[0] is None
        assert connection.execute("SELECT COUNT(*) FROM alert_rules").fetchone()[0] == 3
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE observations SET humidity=101")
    engine = create_engine(f"sqlite:///{database}")
    try:
        with engine.connect() as connection:
            differences = compare_metadata(
                MigrationContext.configure(
                    connection,
                    opts={
                        "include_object": lambda obj, name, kind, reflected, compare_to: (
                            name != "alembic_version"
                        )
                    },
                ),
                Base.metadata,
            )
            assert differences == []
    finally:
        engine.dispose()
    migrate(database, "downgrade", "0001")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT * FROM observations").fetchone() == before
        assert (
            connection.execute("SELECT name FROM sqlite_master WHERE name='users'").fetchone()
            is None
        )


def test_upgrade_rejects_invalid_legacy_data_before_schema_changes(tmp_path):
    database = tmp_path / "invalid.db"
    migrate(database, "upgrade", "0001")
    before = insert_legacy(database, humidity=200)
    result = migrate(database, "upgrade", "head", check=False)
    assert result.returncode != 0
    assert "review data first" in result.stderr
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT * FROM observations").fetchone() == before
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0001"


def test_downgrade_refuses_to_delete_user_data(tmp_path):
    database = tmp_path / "protected.db"
    migrate(database, "upgrade", "head")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO users (id, email, password_hash, full_name) VALUES (?, ?, ?, ?)",
            (uuid4().hex, "person@example.test", "test-only", "Kiểm thử"),
        )
    result = migrate(database, "downgrade", "0001", check=False)
    assert result.returncode != 0
    assert "would delete domain data" in result.stderr
    engine = create_engine(f"sqlite:///{database}")
    try:
        assert "users" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002"


def test_current_revision_creates_shared_timestamps(tmp_path):
    database = tmp_path / "timestamps.db"
    migrate(database, "upgrade", "head")
    engine = create_engine(f"sqlite:///{database}")
    try:
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
        for table_name in Base.metadata.tables:
            columns = {column["name"]: column for column in inspector.get_columns(table_name)}
            for name in ("created_at", "updated_at"):
                assert columns[name]["nullable"] is False
                assert columns[name]["default"] is not None
    finally:
        engine.dispose()
    user_id = uuid4().hex
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO users (id, email, password_hash, full_name) VALUES (?, ?, ?, ?)",
            (user_id, "person@example.test", "test-only", "Kiểm thử"),
        )
        connection.execute(
            "INSERT INTO user_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            ("a" * 64, user_id, "2099-01-01 00:00:00"),
        )
        for table_name in ("users", "user_sessions", "alert_rules"):
            assert (
                connection.execute(
                    f"SELECT COUNT(*) FROM {table_name} "
                    "WHERE created_at IS NULL OR updated_at IS NULL"
                ).fetchone()[0]
                == 0
            )
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002"
