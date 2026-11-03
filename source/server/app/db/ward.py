from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Ward(Base):
    __tablename__ = "wards"
    __table_args__ = (
        Index("ix_wards_province_name", "province_id", "name"),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_wards_coordinate_pair",
        ),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_wards_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_wards_longitude"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    province_id: Mapped[str] = mapped_column(
        ForeignKey("provinces.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    administrative_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(8, 5), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(8, 5), nullable=True)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
