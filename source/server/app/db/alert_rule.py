from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"
    __table_args__ = (
        UniqueConstraint("rule_key", "version", name="uq_alert_rules_version"),
        CheckConstraint("version > 0", name="ck_alert_rules_version"),
        CheckConstraint("operator IN ('gte', 'lte')", name="ck_alert_rules_operator"),
        CheckConstraint(
            "metric IN ('temperature', 'humidity', 'wind_speed', 'rainfall')",
            name="ck_alert_rules_metric",
        ),
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')", name="ck_alert_rules_severity"
        ),
        CheckConstraint("cooldown_seconds >= 0", name="ck_alert_rules_cooldown"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    rule_key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    operator: Mapped[str] = mapped_column(String(8), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
