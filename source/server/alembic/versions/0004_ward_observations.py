"""Reset approved city observations and require Ward-based current ingestion."""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("DELETE FROM observations"))
    with op.batch_alter_table("observations") as batch:
        batch.drop_index("ix_observations_city_time")
        batch.drop_column("city")
        batch.add_column(sa.Column("ward_id", sa.String(20), nullable=False))
        batch.create_foreign_key(
            "fk_observations_ward", "wards", ["ward_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_index("ix_observations_ward_time", ["ward_id", "source", "observed_at"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM observations")):
        raise RuntimeError("Ward observations must be preserved before downgrading")
    with op.batch_alter_table("observations") as batch:
        batch.drop_index("ix_observations_ward_time")
        batch.drop_constraint("fk_observations_ward", type_="foreignkey")
        batch.drop_column("ward_id")
        batch.add_column(sa.Column("city", sa.String(64), nullable=False))
        batch.create_index("ix_observations_city_time", ["city", "observed_at"])
