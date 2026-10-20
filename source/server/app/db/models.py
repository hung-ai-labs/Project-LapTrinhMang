from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (Index("ix_observations_city_time", "city", "observed_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    city: Mapped[str] = mapped_column(String(64))
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    wind_speed: Mapped[float] = mapped_column(Float)
    rainfall: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
