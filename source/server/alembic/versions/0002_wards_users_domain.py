"""Add administrative catalog, users and weather domain tables."""

from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
OBSERVATION_CHECKS = {
    "ck_observations_geography": (
        "(ward_id IS NOT NULL AND city IS NULL) OR (ward_id IS NULL AND city IS NOT NULL)"
    ),
    "ck_observations_source": "source IN ('simulator', 'provider')",
    "ck_observations_temperature": "temperature BETWEEN -60 AND 65",
    "ck_observations_humidity": "humidity BETWEEN 0 AND 100",
    "ck_observations_wind": "wind_speed BETWEEN 0 AND 500",
    "ck_observations_rainfall": "rainfall BETWEEN 0 AND 1000",
}
DEMO_RULES = [
    {
        "id": UUID("c797c69a-6818-4cd4-a24e-7c6a9af13871"),
        "rule_key": "heat",
        "version": 1,
        "metric": "temperature",
        "operator": "gte",
        "threshold": 35.0,
        "severity": "warning",
        "cooldown_seconds": 0,
        "enabled": True,
    },
    {
        "id": UUID("81b51f6d-77f8-48c4-a4d2-527c1b6f492d"),
        "rule_key": "rain",
        "version": 1,
        "metric": "rainfall",
        "operator": "gte",
        "threshold": 20.0,
        "severity": "warning",
        "cooldown_seconds": 0,
        "enabled": True,
    },
    {
        "id": UUID("a12e9aec-f1ec-4f33-b302-c7328ec4460e"),
        "rule_key": "wind",
        "version": 1,
        "metric": "wind_speed",
        "operator": "gte",
        "threshold": 50.0,
        "severity": "warning",
        "cooldown_seconds": 0,
        "enabled": True,
    },
]


def rules_table():
    return sa.table(
        "alert_rules",
        sa.column("id", sa.Uuid()),
        sa.column("rule_key", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("metric", sa.String()),
        sa.column("operator", sa.String()),
        sa.column("threshold", sa.Float()),
        sa.column("severity", sa.String()),
        sa.column("cooldown_seconds", sa.Integer()),
        sa.column("enabled", sa.Boolean()),
    )


def upgrade():
    invalid = op.get_bind().scalar(
        sa.text(
            "SELECT COUNT(*) FROM observations WHERE city IS NULL OR "
            "source NOT IN ('simulator', 'provider') OR temperature NOT BETWEEN -60 AND 65 OR "
            "humidity NOT BETWEEN 0 AND 100 OR wind_speed NOT BETWEEN 0 AND 500 OR "
            "rainfall NOT BETWEEN 0 AND 1000"
        )
    )
    if invalid:
        raise RuntimeError("Existing observations violate the new constraints; review data first")
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rule_key", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("metric", sa.String(length=32), nullable=False),
        sa.Column("operator", sa.String(length=8), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "metric IN ('temperature', 'humidity', 'wind_speed', 'rainfall')",
            name="ck_alert_rules_metric",
        ),
        sa.CheckConstraint("operator IN ('gte', 'lte')", name="ck_alert_rules_operator"),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'critical')", name="ck_alert_rules_severity"
        ),
        sa.CheckConstraint("cooldown_seconds >= 0", name="ck_alert_rules_cooldown"),
        sa.CheckConstraint("version > 0", name="ck_alert_rules_version"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_key", "version", name="uq_alert_rules_version"),
    )
    op.create_table(
        "provinces",
        sa.Column("id", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("dataset_version", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_provinces_name"), "provinces", ["name"], unique=False)
    op.create_table(
        "wards",
        sa.Column("id", sa.String(length=20), nullable=False),
        sa.Column("province_id", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("administrative_type", sa.String(length=32), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=8, scale=5), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=8, scale=5), nullable=True),
        sa.Column("dataset_version", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_wards_coordinate_pair",
        ),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_wards_latitude"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_wards_longitude"),
        sa.ForeignKeyConstraint(["province_id"], ["provinces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wards_province_name", "wards", ["province_id", "name"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("address_text", sa.String(length=500), nullable=True),
        sa.Column("default_ward_id", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("email = lower(trim(email))", name="ck_users_normalized_email"),
        sa.ForeignKeyConstraint(["default_ward_id"], ["wards.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_default_ward_id"), "users", ["default_ward_id"], unique=False)
    op.create_table(
        "user_sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_user_sessions_expiry"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(
        "ix_user_sessions_user_expiry", "user_sessions", ["user_id", "expires_at"], unique=False
    )
    with op.batch_alter_table("observations") as batch:
        batch.add_column(sa.Column("ward_id", sa.String(20), nullable=True))
        batch.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch.alter_column("city", existing_type=sa.String(64), nullable=True)
        batch.alter_column(
            "source", existing_type=sa.String(32), type_=sa.String(16), existing_nullable=False
        )
        batch.create_foreign_key(
            "fk_observations_ward", "wards", ["ward_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_unique_constraint("uq_observations_context", ["id", "ward_id", "source"])
        for name, condition in OBSERVATION_CHECKS.items():
            batch.create_check_constraint(name, condition)
        batch.create_index("ix_observations_ward_time", ["ward_id", "observed_at"])
        batch.create_index("ix_observations_ward_source_time", ["ward_id", "source", "observed_at"])
    op.create_table(
        "forecasts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ward_id", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("last_input_observation_id", sa.String(length=36), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("target_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("predicted_temperature", sa.Float(), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("is_ai", sa.Boolean(), nullable=False),
        sa.Column("fallback_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "method = 'persistence_baseline' AND is_ai = false", name="ck_forecasts_baseline"
        ),
        sa.CheckConstraint("source IN ('simulator', 'provider')", name="ck_forecasts_source"),
        sa.CheckConstraint(
            "input_from <= input_to AND target_at > input_to", name="ck_forecasts_window"
        ),
        sa.ForeignKeyConstraint(
            ["last_input_observation_id", "ward_id", "source"],
            ["observations.id", "observations.ward_id", "observations.source"],
            name="fk_forecasts_input_context",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["ward_id"], ["wards.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_forecasts_ward_source_target",
        "forecasts",
        ["ward_id", "source", "target_at"],
        unique=False,
    )
    op.create_table(
        "weather_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ward_id", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("started_by_observation_id", sa.String(length=36), nullable=False),
        sa.Column("last_observation_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rule_snapshot", sa.JSON(), nullable=False),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "(status = 'active' AND resolved_at IS NULL) OR "
            "(status = 'resolved' AND resolved_at IS NOT NULL)",
            name="ck_weather_alerts_resolution",
        ),
        sa.CheckConstraint("source IN ('simulator', 'provider')", name="ck_weather_alerts_source"),
        sa.CheckConstraint(
            "last_evaluated_at >= started_at AND "
            "(resolved_at IS NULL OR resolved_at >= started_at)",
            name="ck_weather_alerts_times",
        ),
        sa.ForeignKeyConstraint(
            ["last_observation_id", "ward_id", "source"],
            ["observations.id", "observations.ward_id", "observations.source"],
            name="fk_weather_alerts_last_context",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["rule_id"], ["alert_rules.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["started_by_observation_id", "ward_id", "source"],
            ["observations.id", "observations.ward_id", "observations.source"],
            name="fk_weather_alerts_started_context",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["ward_id"], ["wards.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_weather_alerts_status_started", "weather_alerts", ["status", "started_at"], unique=False
    )
    op.create_index(
        "uq_weather_alerts_active",
        "weather_alerts",
        ["ward_id", "source", "rule_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )
    op.bulk_insert(rules_table(), DEMO_RULES)


def downgrade():
    bind = op.get_bind()
    for table_name in ("users", "user_sessions", "forecasts", "weather_alerts"):
        table = sa.table(table_name)
        if bind.scalar(sa.select(sa.func.count()).select_from(table)):
            raise RuntimeError(
                "Downgrade would delete domain data; restore a verified backup instead"
            )
    if bind.scalar(sa.text("SELECT COUNT(*) FROM observations WHERE ward_id IS NOT NULL")):
        raise RuntimeError("Ward observations cannot be downgraded to legacy city data")
    expected = {row["id"]: row for row in DEMO_RULES}
    for row in bind.execute(sa.select(rules_table())).mappings():
        if dict(row) != expected.get(row["id"]):
            raise RuntimeError("Downgrade would delete custom alert rules")
    for table_name in ("weather_alerts", "forecasts", "user_sessions", "users"):
        op.drop_table(table_name)
    with op.batch_alter_table("observations") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("created_at")
        batch.drop_index("ix_observations_ward_time")
        batch.drop_index("ix_observations_ward_source_time")
        for name in OBSERVATION_CHECKS:
            batch.drop_constraint(name, type_="check")
        batch.drop_constraint("fk_observations_ward", type_="foreignkey")
        batch.drop_constraint("uq_observations_context", type_="unique")
        batch.drop_column("ward_id")
        batch.alter_column("city", existing_type=sa.String(64), nullable=False)
        batch.alter_column(
            "source", existing_type=sa.String(16), type_=sa.String(32), existing_nullable=False
        )
    for table_name in ("wards", "provinces", "alert_rules"):
        op.drop_table(table_name)
