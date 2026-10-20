import asyncio
import os
import tempfile

import pytest

# Isolate from .env/Neon. Never use an application database in unit tests.
_test_dir = tempfile.TemporaryDirectory(prefix="weather-tests-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_dir.name}/test.db"
os.environ["ENABLE_TCP"] = "true"
os.environ["TCP_HOST"] = "127.0.0.1"
os.environ["TCP_PORT"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.models import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
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
