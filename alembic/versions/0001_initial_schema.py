"""Create the initial Aquarium Manager schema."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "aquariums",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("volume_liters", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("volume_liters > 0", name="ck_aquariums_volume_positive"),
    )
    op.create_table(
        "parameters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "measurement_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aquarium_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("general_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["aquarium_id"], ["aquariums.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_measurement_sessions_aquarium_timestamp",
        "measurement_sessions",
        ["aquarium_id", "timestamp"],
    )
    op.create_table(
        "measurements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("parameter_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["measurement_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parameter_id"], ["parameters.id"]),
    )
    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aquarium_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["aquarium_id"], ["aquariums.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notes_aquarium_timestamp", "notes", ["aquarium_id", "timestamp"])
    op.create_table(
        "water_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aquarium_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("volume_liters", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "source IN ('RO', 'kran', 'mieszane')",
            name="water_source",
        ),
        sa.CheckConstraint("volume_liters > 0", name="ck_water_changes_volume_positive"),
        sa.ForeignKeyConstraint(["aquarium_id"], ["aquariums.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_water_changes_aquarium_timestamp", "water_changes", ["aquarium_id", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_water_changes_aquarium_timestamp", table_name="water_changes")
    op.drop_table("water_changes")
    op.drop_index("ix_notes_aquarium_timestamp", table_name="notes")
    op.drop_table("notes")
    op.drop_table("measurements")
    op.drop_index("ix_measurement_sessions_aquarium_timestamp", table_name="measurement_sessions")
    op.drop_table("measurement_sessions")
    op.drop_table("parameters")
    op.drop_table("aquariums")
