"""Add fertilizer default target increase."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006_fertilizer_default_target"
down_revision: str | None = "0005_fertilizer_applications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fertilizers",
        sa.Column(
            "default_target_increase_ppm",
            sa.Float(),
            server_default=sa.text("5.0"),
            nullable=False,
        )
    )


def downgrade() -> None:
    op.drop_column("fertilizers", "default_target_increase_ppm")
