import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, Province, Ward
from app.schemas.geography import NearestWardInput
from app.services.geography import (
    WardPoint,
    haversine_km,
    nearest_active_ward,
    nearest_ward,
)


def test_nearest_ward_selects_shortest_distance():
    result = nearest_ward(
        21.0,
        105.0,
        [
            WardPoint("far", 22.0, 105.0),
            WardPoint("near", 21.001, 105.0),
        ],
    )
    assert result.ward_id == "near"
    assert result.distance_km == pytest.approx(0.111195, abs=0.00001)


def test_equal_coordinates_have_stable_tie_break():
    result = nearest_ward(
        21.0,
        105.0,
        [
            WardPoint("test-w2", 21.0, 105.0),
            WardPoint("test-w1", 21.0, 105.0),
        ],
    )
    assert result.ward_id == "test-w1"
    assert result.distance_km == 0


def test_empty_candidates_and_valid_zero_coordinates():
    assert nearest_ward(21.0, 105.0, []) is None
    assert haversine_km(0.0, 0.0, 0.0, 1.0) == pytest.approx(111.19508, abs=0.0001)


@pytest.mark.parametrize(
    "latitude,longitude",
    [
        (91.0, 105.0),
        (-91.0, 105.0),
        (21.0, 181.0),
        (21.0, -181.0),
        (float("nan"), 105.0),
        (21.0, float("inf")),
    ],
)
def test_invalid_coordinates_rejected(latitude, longitude):
    with pytest.raises(ValidationError):
        NearestWardInput(latitude=latitude, longitude=longitude)
    with pytest.raises(ValueError):
        nearest_ward(latitude, longitude, [])


def test_only_active_wards_with_coordinates_are_candidates(tmp_path):
    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'geography.db'}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add_all(
                    [
                        Province(id="active-p", name="Tỉnh kiểm thử", dataset_version="test"),
                        Province(
                            id="inactive-p", name="Tỉnh cũ", dataset_version="test", is_active=False
                        ),
                    ]
                )
                await session.flush()
                for code, province_id, active, latitude, longitude in [
                    ("eligible", "active-p", True, "21.001", "105"),
                    ("inactive-ward", "active-p", False, "21", "105"),
                    ("inactive-province", "inactive-p", True, "21", "105"),
                    ("missing-coordinates", "active-p", True, None, None),
                ]:
                    session.add(
                        Ward(
                            id=code,
                            province_id=province_id,
                            name=code,
                            administrative_type=None,
                            dataset_version="test",
                            is_active=active,
                            latitude=Decimal(latitude) if latitude is not None else None,
                            longitude=Decimal(longitude) if longitude is not None else None,
                        )
                    )
                await session.commit()
                result = await nearest_active_ward(session, 21.0, 105.0)
                assert result.ward_id == "eligible"
        finally:
            await engine.dispose()

    asyncio.run(scenario())
