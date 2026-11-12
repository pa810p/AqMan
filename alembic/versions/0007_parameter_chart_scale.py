"""Add configurable parameter chart scales."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0007_parameter_chart_scale"
down_revision: str | None = "0006_fertilizer_default_target"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("parameters") as batch_op:
        batch_op.add_column(sa.Column("chart_min_value", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("chart_max_value", sa.Float(), nullable=True))
        batch_op.create_check_constraint(
            "ck_parameters_chart_scale_order",
            "chart_min_value IS NULL OR chart_max_value IS NULL "
            "OR chart_min_value < chart_max_value",
        )


def downgrade() -> None:
    with op.batch_alter_table("parameters") as batch_op:
        batch_op.drop_constraint("ck_parameters_chart_scale_order", type_="check")
        batch_op.drop_column("chart_max_value")
        batch_op.drop_column("chart_min_value")
