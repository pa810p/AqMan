"""Add fertilizer application history."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_fertilizer_applications"
down_revision: str | None = "0004_fertilizer_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fertilizer_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aquarium_id", sa.Integer(), nullable=False),
        sa.Column("fertilizer_id", sa.Integer(), nullable=False),
        sa.Column("actual_dose_ml", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "actual_dose_ml > 0",
            name="ck_fertilizer_applications_dose_positive",
        ),
        sa.ForeignKeyConstraint(
            ["aquarium_id"],
            ["aquariums.id"],
            name="fk_fertilizer_applications_aquarium_id_aquariums",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["fertilizer_id"],
            ["fertilizers.id"],
            name="fk_fertilizer_applications_fertilizer_id_fertilizers",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fertilizer_applications_aquarium_timestamp",
        "fertilizer_applications",
        ["aquarium_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fertilizer_applications_aquarium_timestamp",
        table_name="fertilizer_applications",
    )
    op.drop_table("fertilizer_applications")
