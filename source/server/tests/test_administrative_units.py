import asyncio
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, Province, User, Ward
from app.services.administrative_units import (
    AdministrativeSnapshot,
    apply_snapshot,
    load_snapshot,
)

DATA_DIRECTORY = Path(__file__).resolve().parents[2] / "data" / "administrative"


def catalog(**changes):
    return {
        "dataset_version": "test-v1",
        "provinces": [{"id": "01", "name": "Tỉnh kiểm thử"}],
        "wards": [
            {
                "id": "00001",
                "province_id": "01",
                "name": "Phường kiểm thử",
                "latitude": "21",
                "longitude": "105",
            }
        ],
        **changes,
    }


def test_bundled_snapshot_has_verified_hash_counts_and_coordinates():
    snapshot = load_snapshot(DATA_DIRECTORY / "snapshot.json", DATA_DIRECTORY / "manifest.json")
    assert len(snapshot.provinces) == 34
    assert len(snapshot.wards) == 3321
    assert all(row.latitude is not None and row.longitude is not None for row in snapshot.wards)
    assert snapshot.provinces[0].id == "01"
    assert snapshot.wards[0].id.startswith("0")
    assert snapshot.wards[0].administrative_type is None


@pytest.mark.parametrize(
    "changes",
    [
        {"provinces": [{"id": "01", "name": "A"}, {"id": "01", "name": "B"}]},
        {"wards": [{"id": "01", "province_id": "missing", "name": "A"}]},
        {"wards": [{"id": "01", "province_id": "01", "name": "A", "latitude": "21"}]},
        {
            "wards": [
                {
                    "id": "01",
                    "province_id": "01",
                    "name": "A",
                    "latitude": "NaN",
                    "longitude": "105",
                }
            ]
        },
        {
            "wards": [
                {
                    "id": "01",
                    "province_id": "01",
                    "name": "A",
                    "latitude": "91",
                    "longitude": "105",
                }
            ]
        },
    ],
)
def test_invalid_catalog_is_rejected(changes):
    with pytest.raises(ValidationError):
        AdministrativeSnapshot.model_validate(catalog(**changes))


def test_snapshot_tampering_is_rejected(tmp_path):
    payload = json.dumps(catalog()).encode()
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_bytes(payload + b" ")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"snapshot_sha256": hashlib.sha256(payload).hexdigest()}))
    with pytest.raises(ValueError, match="SHA-256"):
        load_snapshot(snapshot_path, manifest_path)


def test_import_is_idempotent_and_keeps_referenced_inactive_wards(tmp_path):
    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'catalog.db'}")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            first = AdministrativeSnapshot.model_validate(catalog())
            async with factory.begin() as session:
                await apply_snapshot(session, first)
                await apply_snapshot(session, first)
                session.add(
                    User(
                        id=str(uuid4()),
                        email="person@example.test",
                        name="Kiểm thử",
                        password_hash="test-only",
                        default_ward_id="00001",
                    )
                )
            second = AdministrativeSnapshot.model_validate(
                catalog(
                    dataset_version="test-v2",
                    provinces=[{"id": "02", "name": "Tỉnh mới kiểm thử"}],
                    wards=[{"id": "00002", "province_id": "02", "name": "Xã mới kiểm thử"}],
                )
            )
            async with factory.begin() as session:
                await apply_snapshot(session, second)
            async with factory() as session:
                assert len((await session.scalars(select(Ward))).all()) == 2
                assert (await session.get(Ward, "00001")).is_active is False
                assert (await session.get(Province, "01")).is_active is False
                assert (await session.get(Ward, "00002")).is_active is True
                user = await session.scalar(select(User))
                assert user.default_ward_id == "00001"
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_database_failure_rolls_back_the_entire_catalog(tmp_path):
    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'rollback.db'}")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
                await connection.exec_driver_sql(
                    "CREATE TRIGGER reject_ward BEFORE INSERT ON wards "
                    "BEGIN SELECT RAISE(ABORT, 'test failure'); END"
                )
            snapshot = AdministrativeSnapshot.model_validate(catalog())
            with pytest.raises(IntegrityError):
                async with factory.begin() as session:
                    await apply_snapshot(session, snapshot)
            async with factory() as session:
                assert (await session.scalars(select(Province))).all() == []
                assert (await session.scalars(select(Ward))).all() == []
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_full_bundled_catalog_can_be_imported_twice(tmp_path):
    snapshot = load_snapshot(DATA_DIRECTORY / "snapshot.json", DATA_DIRECTORY / "manifest.json")

    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'full-catalog.db'}")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            for _ in range(2):
                async with factory.begin() as session:
                    await apply_snapshot(session, snapshot)
            async with factory() as session:
                assert len((await session.scalars(select(Province))).all()) == 34
                assert len((await session.scalars(select(Ward))).all()) == 3321
                match = await session.get(Ward, "00004")
                assert match.province_id == "01"
                assert str(match.latitude) == "21.04000"
        finally:
            await engine.dispose()

    asyncio.run(scenario())
