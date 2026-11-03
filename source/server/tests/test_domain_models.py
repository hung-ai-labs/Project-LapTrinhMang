from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import (
    AlertRule,
    Base,
    Forecast,
    Province,
    User,
    UserSession,
    Ward,
    WeatherAlert,
    WeatherObservation,
)
from app.schemas.weather import ObservationOut


@pytest.fixture
def schema_engine():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def add_ward(session, code="test-w1", name="Phường kiểm thử"):
    if session.get(Province, "test-p") is None:
        session.add(Province(id="test-p", name="Tỉnh kiểm thử", dataset_version="test-v1"))
        session.flush()
    ward = Ward(
        id=code,
        name=name,
        province_id="test-p",
        administrative_type="ward",
        latitude=Decimal("21.00000"),
        longitude=Decimal("105.00000"),
        dataset_version="test-v1",
    )
    session.add(ward)
    session.flush()
    return ward


def test_metadata_excludes_location_and_data_source():
    assert set(Base.metadata.tables) == {
        "provinces",
        "wards",
        "users",
        "user_sessions",
        "observations",
        "alert_rules",
        "weather_alerts",
        "forecasts",
    }
    for table in Base.metadata.tables.values():
        assert "location_id" not in table.c
        assert "source_id" not in table.c
        assert "model_version_id" not in table.c


def test_every_model_inherits_both_timestamps_from_base():
    for mapper in Base.registry.mappers:
        assert issubclass(mapper.class_, Base)
        assert "created_at" not in mapper.class_.__annotations__
        assert "updated_at" not in mapper.class_.__annotations__
        table = mapper.local_table
        assert table.c.created_at.nullable is False
        assert table.c.updated_at.nullable is False
        assert table.c.created_at.server_default is not None
        assert table.c.updated_at.server_default is not None
        assert table.c.updated_at.onupdate is not None


def test_timestamp_defaults_and_orm_updates(schema_engine):
    with Session(schema_engine) as session:
        ward = add_ward(session)
        session.commit()
        session.refresh(ward)
        assert ward.created_at is not None
        assert ward.updated_at is not None
        old_time = datetime(2000, 1, 1)
        ward.created_at = old_time
        ward.updated_at = old_time
        session.commit()
        ward.name = "Tên được cập nhật"
        session.commit()
        session.refresh(ward)
        assert ward.created_at == old_time
        assert ward.updated_at > old_time


def test_default_ward_and_coordinates_survive_reload(schema_engine):
    with Session(schema_engine) as session:
        ward = add_ward(session)
        user = User(
            email="person@example.test",
            full_name="Kiểm thử",
            password_hash="test-only",
            default_ward_id=ward.id,
            address_text="Địa chỉ riêng kiểm thử",
        )
        session.add(user)
        session.commit()
        user_id = user.id
    with Session(schema_engine) as session:
        restored = session.get(User, user_id)
        ward = session.get(Ward, restored.default_ward_id)
        assert ward.id == "test-w1"
        assert ward.latitude == Decimal("21.00000")
        assert ward.province_id == "test-p"
        assert restored.address_text == "Địa chỉ riêng kiểm thử"


def test_ward_requires_existing_province(schema_engine):
    with Session(schema_engine) as session:
        session.add(
            Ward(
                id="test-w",
                province_id="missing",
                name="Kiểm thử",
                administrative_type="ward",
                dataset_version="test-v1",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_weather_remains_after_deleting_user(schema_engine):
    now = datetime.now(UTC)
    with Session(schema_engine) as session:
        ward = add_ward(session)
        user = User(
            email="person@example.test",
            full_name="Kiểm thử",
            password_hash="test-only",
            default_ward_id=ward.id,
        )
        session.add(user)
        session.flush()
        observation = WeatherObservation(
            id=str(uuid4()),
            ward_id=ward.id,
            legacy_city=None,
            temperature=30,
            humidity=70,
            wind_speed=10,
            rainfall=0,
            source="simulator",
            observed_at=now,
        )
        session.add(observation)
        session.add(
            UserSession(
                token_hash="a" * 64,
                user_id=user.id,
                created_at=now,
                expires_at=now + timedelta(days=7),
            )
        )
        session.commit()
        observation_id = observation.id
        session.delete(user)
        session.commit()
        session.expire_all()
        assert session.get(UserSession, "a" * 64) is None
        assert session.get(WeatherObservation, observation_id).ward_id == "test-w1"
        session.delete(session.get(Ward, "test-w1"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_legacy_city_data_is_not_assigned_to_a_ward(schema_engine):
    with Session(schema_engine) as session:
        observation = WeatherObservation(
            id=str(uuid4()),
            ward_id=None,
            legacy_city="hanoi",
            temperature=30,
            humidity=70,
            wind_speed=10,
            rainfall=0,
            source="simulator",
            observed_at=datetime.now(UTC),
        )
        session.add(observation)
        session.commit()
        assert session.get(WeatherObservation, observation.id).ward_id is None
        assert (
            session.scalars(
                select(WeatherObservation).where(WeatherObservation.ward_id == "test-w1")
            ).all()
            == []
        )
        output = ObservationOut.model_validate(observation)
        assert output.city == "hanoi"
        assert ObservationOut.model_validate(output.model_dump()).city == "hanoi"


def add_observation(session):
    ward = add_ward(session)
    now = datetime.now(UTC)
    record = WeatherObservation(
        id=str(uuid4()),
        ward_id=ward.id,
        source="simulator",
        observed_at=now,
        temperature=30,
        humidity=70,
        wind_speed=10,
        rainfall=0,
    )
    session.add(record)
    session.flush()
    return record


@pytest.mark.parametrize("wrong_context", ["ward", "source"])
def test_forecast_rejects_input_from_a_different_ward_or_source(schema_engine, wrong_context):
    with Session(schema_engine) as session:
        observation = add_observation(session)
        another = add_ward(session, code="test-w2")
        session.add(
            Forecast(
                ward_id=another.id if wrong_context == "ward" else observation.ward_id,
                source="provider" if wrong_context == "source" else observation.source,
                last_input_observation_id=observation.id,
                input_from=observation.observed_at,
                input_to=observation.observed_at,
                target_at=observation.observed_at + timedelta(hours=1),
                predicted_temperature=30,
                method="persistence_baseline",
                is_ai=False,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_forecast_supports_only_the_current_baseline(schema_engine):
    with Session(schema_engine) as session:
        observation = add_observation(session)
        values = {
            "ward_id": observation.ward_id,
            "source": observation.source,
            "last_input_observation_id": observation.id,
            "input_from": observation.observed_at,
            "input_to": observation.observed_at,
            "target_at": observation.observed_at + timedelta(hours=1),
            "predicted_temperature": 30,
        }
        session.add(Forecast(**values, method="persistence_baseline", is_ai=False))
        session.commit()
        session.add(Forecast(**values, method="model", is_ai=True))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_only_one_active_alert_episode_per_ward_source_and_rule(schema_engine):
    with Session(schema_engine) as session:
        observation = add_observation(session)
        rule = AlertRule(
            rule_key="heat",
            version=1,
            metric="temperature",
            operator="gte",
            threshold=35,
            severity="warning",
        )
        session.add(rule)
        session.flush()
        values = {
            "ward_id": observation.ward_id,
            "source": observation.source,
            "rule_id": rule.id,
            "started_by_observation_id": observation.id,
            "started_at": observation.observed_at,
            "last_evaluated_at": observation.observed_at,
            "rule_snapshot": {"threshold": 35},
        }
        session.add(WeatherAlert(**values, status="active"))
        session.commit()
        session.add(WeatherAlert(**values, status="active"))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
