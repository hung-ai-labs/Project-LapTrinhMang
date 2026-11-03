from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base, Province, User, Ward


@pytest.fixture
def schema_engine():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_models_have_shared_timestamps():
    assert set(Base.metadata.tables) == {"users", "observations", "provinces", "wards"}
    for mapper in Base.registry.mappers:
        assert issubclass(mapper.class_, Base)
        assert "created_at" not in mapper.class_.__annotations__
        assert "updated_at" not in mapper.class_.__annotations__
        assert mapper.local_table.c.updated_at.onupdate is not None


def test_foreign_key_rejects_missing_province(schema_engine):
    with Session(schema_engine) as session:
        session.add(
            Ward(id="test-w", name="Xã kiểm thử", province_id="missing", dataset_version="test")
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_shared_updated_at_changes_without_replacing_created_at(schema_engine):
    with Session(schema_engine) as session:
        old = datetime(2000, 1, 1)
        province = Province(
            id="test-p", name="Tên cũ", dataset_version="test", created_at=old, updated_at=old
        )
        session.add(province)
        session.commit()
        province.name = "Tên mới"
        session.commit()
        session.refresh(province)
        assert province.created_at == old
        assert province.updated_at > old


def test_saved_ward_survives_reload_and_restricts_deletion(schema_engine):
    with Session(schema_engine) as session:
        session.add(Province(id="01", name="Tỉnh kiểm thử", dataset_version="test"))
        session.flush()
        session.add(Ward(id="00001", name="Xã kiểm thử", province_id="01", dataset_version="test"))
        session.flush()
        user_id = str(uuid4())
        session.add(
            User(
                id=user_id,
                name="User từ main",
                email="person@example.com",
                password_hash="test-only",
                default_ward_id="00001",
                address_text="Địa chỉ riêng kiểm thử",
            )
        )
        session.commit()
    with Session(schema_engine) as session:
        user = session.get(User, user_id)
        assert user.default_ward_id == "00001"
        assert user.address_text == "Địa chỉ riêng kiểm thử"
        assert user.token_version == 0
        session.delete(session.get(Ward, "00001"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


@pytest.mark.parametrize("latitude,longitude", [(91, 105), (21, 181), (21, None)])
def test_ward_coordinate_constraints(schema_engine, latitude, longitude):
    with Session(schema_engine) as session:
        session.add(Province(id="01", name="Tỉnh kiểm thử", dataset_version="test"))
        session.flush()
        session.add(
            Ward(
                id="00001",
                name="Xã kiểm thử",
                province_id="01",
                dataset_version="test",
                latitude=latitude,
                longitude=longitude,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_ward_names_can_repeat_with_different_codes(schema_engine):
    with Session(schema_engine) as session:
        for code in ("01", "02"):
            session.add(Province(id=code, name=code, dataset_version="test"))
        session.flush()
        for code in ("01", "02"):
            session.add(
                Ward(id=code, province_id=code, name="Tên xã trùng nhau", dataset_version="test")
            )
        session.commit()
