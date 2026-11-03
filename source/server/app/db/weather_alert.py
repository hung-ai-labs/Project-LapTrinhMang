from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class WeatherAlert(Base):
    __tablename__ = "weather_alerts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["started_by_observation_id", "ward_id", "source"],
            ["observations.id", "observations.ward_id", "observations.source"],
            ondelete="RESTRICT",
            name="fk_weather_alerts_started_context",
        ),
        ForeignKeyConstraint(
            ["last_observation_id", "ward_id", "source"],
            ["observations.id", "observations.ward_id", "observations.source"],
            ondelete="RESTRICT",
            name="fk_weather_alerts_last_context",
        ),
        CheckConstraint("source IN ('simulator', 'provider')", name="ck_weather_alerts_source"),
        CheckConstraint(
            "(status = 'active' AND resolved_at IS NULL) OR "
            "(status = 'resolved' AND resolved_at IS NOT NULL)",
            name="ck_weather_alerts_resolution",
        ),
        CheckConstraint(
            "last_evaluated_at >= started_at AND "
            "(resolved_at IS NULL OR resolved_at >= started_at)",
            name="ck_weather_alerts_times",
        ),
        Index(
            "uq_weather_alerts_active",
            "ward_id",
            "source",
            "rule_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        Index("ix_weather_alerts_status_started", "status", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    ward_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("wards.id", ondelete="RESTRICT"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("alert_rules.id", ondelete="RESTRICT"), nullable=False
    )
    started_by_observation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    last_observation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rule_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
