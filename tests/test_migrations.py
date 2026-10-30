from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from aqman.migrations import upgrade_database


def _alembic_config(database_url: str, project_root: Path) -> Config:
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def test_measurement_session_data_migrates_to_direct_measurements(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'legacy.sqlite3'}"
    project_root = Path(__file__).resolve().parents[1]
    config = _alembic_config(database_url, project_root)
    command.upgrade(config, "0002_aquarium_thumbnail")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO aquariums (id, name, volume_liters, created_at, active)
                VALUES (1, 'Test', 40, '2026-10-30 08:00:00.000000', 1)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO parameters (id, name, unit)
                VALUES (1, 'pH', '—'), (2, 'NO3', 'mg/L')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO measurement_sessions (id, aquarium_id, timestamp, general_note)
                VALUES (1, 1, '2026-10-30 10:00:00.000000', 'Shared note')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO measurements (id, session_id, parameter_id, value, note)
                VALUES
                    (1, 1, 1, 7.1, 'First reading'),
                    (2, 1, 2, 12.5, NULL)
                """
            )
        )
    engine.dispose()

    upgrade_database(database_url, project_root)

    engine = create_engine(database_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    measurement_columns = {column["name"] for column in inspector.get_columns("measurements")}
    with engine.connect() as connection:
        measurements = connection.execute(
            text(
                """
                SELECT aquarium_id, timestamp, parameter_id, value, note
                FROM measurements
                ORDER BY id
                """
            )
        ).all()
        notes = connection.execute(text("SELECT content FROM notes ORDER BY id")).scalars().all()
    engine.dispose()

    assert "measurement_sessions" not in table_names
    assert {"aquarium_id", "timestamp"} <= measurement_columns
    assert "session_id" not in measurement_columns
    assert [row[0] for row in measurements] == [1, 1]
    assert all(row[1].startswith("2026-10-30 10:00:00") for row in measurements)
    assert [(row[2], row[3], row[4]) for row in measurements] == [
        (1, 7.1, "First reading"),
        (2, 12.5, None),
    ]
    assert notes == ["Shared note"]

    command.downgrade(config, "0002_aquarium_thumbnail")

    engine = create_engine(database_url)
    downgraded_tables = set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        downgraded_measurements = connection.execute(
            text("SELECT session_id FROM measurements ORDER BY id")
        ).scalars().all()
    engine.dispose()

    assert "measurement_sessions" in downgraded_tables
    assert len(downgraded_measurements) == 2
    assert len(set(downgraded_measurements)) == 2
