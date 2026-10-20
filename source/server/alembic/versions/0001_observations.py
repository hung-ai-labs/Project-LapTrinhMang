"""Create weather observations."""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("city", sa.String(64), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("humidity", sa.Float(), nullable=False),
        sa.Column("wind_speed", sa.Float(), nullable=False),
        sa.Column("rainfall", sa.Float(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_observations_city_time", "observations", ["city", "observed_at"])


def downgrade():
    op.drop_index("ix_observations_city_time", table_name="observations")
    op.drop_table("observations")
