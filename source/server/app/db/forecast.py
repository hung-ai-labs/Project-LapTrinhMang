from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class Forecast(Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["last_input_observation_id", "ward_id", "source"],
            ["observations.id", "observations.ward_id", "observations.source"],
            ondelete="RESTRICT",
            name="fk_forecasts_input_context",
        ),
        CheckConstraint("source IN ('simulator', 'provider')", name="ck_forecasts_source"),
        CheckConstraint(
            "method = 'persistence_baseline' AND is_ai = false",
            name="ck_forecasts_baseline",
        ),
        CheckConstraint(
            "input_from <= input_to AND target_at > input_to", name="ck_forecasts_window"
        ),
        Index("ix_forecasts_ward_source_target", "ward_id", "source", "target_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    ward_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("wards.id", ondelete="RESTRICT"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    last_input_observation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    target_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    predicted_temperature: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    is_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
