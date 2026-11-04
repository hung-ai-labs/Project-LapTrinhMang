"""Add the geographic catalog and shared model timestamps."""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
        for name in ("created_at", "updated_at")
    ]


def upgrade():
    op.create_table(
        "provinces",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("dataset_version", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_provinces_name", "provinces", ["name"])
    op.create_table(
        "wards",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("province_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("administrative_type", sa.String(32), nullable=True),
        sa.Column("latitude", sa.Numeric(8, 5), nullable=True),
        sa.Column("longitude", sa.Numeric(8, 5), nullable=True),
        sa.Column("dataset_version", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["province_id"], ["provinces.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_wards_coordinate_pair",
        ),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_wards_latitude"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_wards_longitude"),
    )
    op.create_index("ix_wards_province_name", "wards", ["province_id", "name"])
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("address_text", sa.String(500), nullable=True))
        batch.add_column(sa.Column("default_ward_id", sa.String(20), nullable=True))
        batch.add_column(timestamps()[1])
        batch.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=sa.func.now(),
        )
        batch.create_foreign_key(
            "fk_users_default_ward", "wards", ["default_ward_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_index("ix_users_default_ward_id", ["default_ward_id"])
    op.execute(sa.text("UPDATE users SET updated_at = created_at"))
    with op.batch_alter_table("observations") as batch:
        for column in timestamps():
            batch.add_column(column)


def downgrade():
    bind = op.get_bind()
    if bind.scalar(
        sa.text(
            "SELECT COUNT(*) FROM users "
            "WHERE default_ward_id IS NOT NULL OR address_text IS NOT NULL"
        )
    ):
        raise RuntimeError("Saved user locations must be preserved before downgrading")
    for table_name in ("wards", "provinces"):
        if bind.scalar(sa.select(sa.func.count()).select_from(sa.table(table_name))):
            raise RuntimeError("Administrative data must be preserved before downgrading")
    with op.batch_alter_table("observations") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("created_at")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_default_ward_id")
        batch.drop_constraint("fk_users_default_ward", type_="foreignkey")
        batch.drop_column("default_ward_id")
        batch.drop_column("address_text")
        batch.drop_column("updated_at")
        batch.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=None,
        )
    op.drop_table("wards")
    op.drop_table("provinces")
