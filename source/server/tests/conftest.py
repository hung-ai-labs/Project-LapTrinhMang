import asyncio
import os
import tempfile
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

os.environ["JWT_SECRET"] = "test-only-secret-key-of-at-least-32-characters"
os.environ["WEATHER_SOURCE"] = "simulator"

# Isolate from .env/Neon. Never use an application database in unit tests.
_test_dir = tempfile.TemporaryDirectory(prefix="weather-tests-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_dir.name}/test.db"
os.environ["ENABLE_TCP"] = "true"
os.environ["TCP_HOST"] = "127.0.0.1"
os.environ["TCP_PORT"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, Observation, Province, Ward  # noqa: E402
from app.db.session import Session, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    async def reset():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(reset())
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def public_data(client):
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
            for code, province, name, active in (
                ("001", "01", "Phường trùng tên", True),
                ("002", "01", "Phường trùng tên", True),
                ("003", "01", "Xã A", True),
                ("004", "01", "Phường ẩn", False),
                ("005", "02", "Phường B", True),
                ("006", "03", "Phường thuộc tỉnh ẩn", True),
            ):
                session.add(
                    Ward(
                        id=code,
                        province_id=province,
                        name=name,
                        is_active=active,
                        latitude=21,
                        longitude=105,
                        dataset_version="test",
                    )
                )
            start = datetime(2026, 10, 20, tzinfo=UTC)
            for number, city, source, minutes in (
                (1, "hanoi", "simulator", 0),
                (2, "hanoi", "simulator", 1),
                (3, "hanoi", "simulator", 1),
                (4, "hanoi", "provider", 2),
                (5, "danang", "simulator", 3),
            ):
                session.add(
                    Observation(
                        id=str(UUID(int=number)),
                        city=city,
                        source=source,
                        temperature=30,
                        humidity=70,
                        wind_speed=10,
                        rainfall=0,
                        observed_at=start + timedelta(minutes=minutes),
                    )
                )
        await engine.dispose()

    asyncio.run(run())
