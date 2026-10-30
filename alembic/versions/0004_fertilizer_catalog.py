"""Add fertilizer catalog and effects."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_fertilizer_catalog"
down_revision: str | None = "0003_direct_measurements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fertilizers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("dose_ml_per_100l", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "dose_ml_per_100l > 0",
            name="ck_fertilizers_dose_positive",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_fertilizers_name_lower",
        "fertilizers",
        [sa.text("lower(name)")],
        unique=True,
    )
    op.create_table(
        "fertilizer_effects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fertilizer_id", sa.Integer(), nullable=False),
        sa.Column("parameter_id", sa.Integer(), nullable=False),
        sa.Column("ppm_per_dose", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "ppm_per_dose > 0",
            name="ck_fertilizer_effects_ppm_positive",
        ),
        sa.ForeignKeyConstraint(
            ["fertilizer_id"],
            ["fertilizers.id"],
            name="fk_fertilizer_effects_fertilizer_id_fertilizers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parameter_id"],
            ["parameters.id"],
            name="fk_fertilizer_effects_parameter_id_parameters",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fertilizer_id",
            "parameter_id",
            name="uq_fertilizer_effects_fertilizer_parameter",
        ),
    )


def downgrade() -> None:
    op.drop_table("fertilizer_effects")
    op.drop_index("uq_fertilizers_name_lower", table_name="fertilizers")
    op.drop_table("fertilizers")
