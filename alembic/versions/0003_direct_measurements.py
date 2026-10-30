"""Store aquarium and timestamp directly on measurements."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_direct_measurements"
down_revision: str | None = "0002_aquarium_thumbnail"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade() -> None:
    op.add_column("measurements", sa.Column("aquarium_id", sa.Integer(), nullable=True))
    op.add_column("measurements", sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE measurements
            SET aquarium_id = (
                    SELECT aquarium_id
                    FROM measurement_sessions
                    WHERE measurement_sessions.id = measurements.session_id
                ),
                timestamp = (
                    SELECT timestamp
                    FROM measurement_sessions
                    WHERE measurement_sessions.id = measurements.session_id
                )
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO notes (aquarium_id, timestamp, category, content)
            SELECT aquarium_id, timestamp, NULL, general_note
            FROM measurement_sessions
            WHERE general_note IS NOT NULL AND TRIM(general_note) != ''
            """
        )
    )

    with op.batch_alter_table(
        "measurements",
        naming_convention=_FK_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_measurements_session_id_measurement_sessions",
            type_="foreignkey",
        )
        batch_op.drop_column("session_id")
        batch_op.alter_column(
            "aquarium_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.alter_column(
            "timestamp",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_measurements_aquarium_id_aquariums",
            "aquariums",
            ["aquarium_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "ix_measurements_aquarium_timestamp",
            ["aquarium_id", "timestamp"],
        )

    op.drop_index(
        "ix_measurement_sessions_aquarium_timestamp",
        table_name="measurement_sessions",
    )
    op.drop_table("measurement_sessions")


def downgrade() -> None:
    op.create_table(
        "measurement_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aquarium_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("general_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["aquarium_id"],
            ["aquariums.id"],
            name="fk_measurement_sessions_aquarium_id_aquariums",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_measurement_sessions_aquarium_timestamp",
        "measurement_sessions",
        ["aquarium_id", "timestamp"],
    )
    op.add_column("measurements", sa.Column("session_id", sa.Integer(), nullable=True))

    bind = op.get_bind()
    measurements = sa.table(
        "measurements",
        sa.column("id", sa.Integer()),
        sa.column("aquarium_id", sa.Integer()),
        sa.column("timestamp", sa.DateTime(timezone=True)),
        sa.column("session_id", sa.Integer()),
    )
    measurement_sessions = sa.Table(
        "measurement_sessions",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aquarium_id", sa.Integer()),
        sa.Column("timestamp", sa.DateTime(timezone=True)),
        sa.Column("general_note", sa.Text()),
    )
    rows = bind.execute(
        sa.select(
            measurements.c.id,
            measurements.c.aquarium_id,
            measurements.c.timestamp,
        )
    ).mappings().all()
    for row in rows:
        session_result = bind.execute(
            sa.insert(measurement_sessions).values(
                aquarium_id=row["aquarium_id"],
                timestamp=row["timestamp"],
                general_note=None,
            )
        )
        bind.execute(
            sa.update(measurements)
            .where(measurements.c.id == row["id"])
            .values(session_id=session_result.inserted_primary_key[0])
        )

    with op.batch_alter_table(
        "measurements",
        naming_convention=_FK_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_index("ix_measurements_aquarium_timestamp")
        batch_op.drop_constraint(
            "fk_measurements_aquarium_id_aquariums",
            type_="foreignkey",
        )
        batch_op.drop_column("aquarium_id")
        batch_op.drop_column("timestamp")
        batch_op.alter_column(
            "session_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_measurements_session_id_measurement_sessions",
            "measurement_sessions",
            ["session_id"],
            ["id"],
            ondelete="CASCADE",
        )
