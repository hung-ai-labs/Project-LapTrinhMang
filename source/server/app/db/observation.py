from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (Index("ix_observations_ward_time", "ward_id", "source", "observed_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ward_id: Mapped[str] = mapped_column(
        ForeignKey("wards.id", ondelete="RESTRICT"), nullable=False
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float] = mapped_column(Float, nullable=False)
    wind_speed: Mapped[float] = mapped_column(Float, nullable=False)
    rainfall: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
