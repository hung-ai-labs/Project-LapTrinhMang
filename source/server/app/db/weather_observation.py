from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WeatherObservation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        CheckConstraint(
            "(ward_id IS NOT NULL AND city IS NULL) OR (ward_id IS NULL AND city IS NOT NULL)",
            name="ck_observations_geography",
        ),
        Index("ix_observations_city_time", "city", "observed_at"),
        UniqueConstraint("id", "ward_id", "source", name="uq_observations_context"),
        CheckConstraint("source IN ('simulator', 'provider')", name="ck_observations_source"),
        CheckConstraint("temperature BETWEEN -60 AND 65", name="ck_observations_temperature"),
        CheckConstraint("humidity BETWEEN 0 AND 100", name="ck_observations_humidity"),
        CheckConstraint("wind_speed BETWEEN 0 AND 500", name="ck_observations_wind"),
        CheckConstraint("rainfall BETWEEN 0 AND 1000", name="ck_observations_rainfall"),
        Index("ix_observations_ward_time", "ward_id", "observed_at"),
        Index("ix_observations_ward_source_time", "ward_id", "source", "observed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ward_id: Mapped[str | None] = mapped_column(
        String(20),
        ForeignKey("wards.id", ondelete="RESTRICT", name="fk_observations_ward"),
        nullable=True,
    )
    legacy_city: Mapped[str | None] = mapped_column("city", String(64), nullable=True)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float] = mapped_column(Float, nullable=False)
    wind_speed: Mapped[float] = mapped_column(Float, nullable=False)
    rainfall: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
