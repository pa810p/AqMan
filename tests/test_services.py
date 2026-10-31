from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import inspect

from aqman.database import Base, create_database_engine, create_session_factory
from aqman.migrations import upgrade_database
from aqman.models import WaterSource
from aqman.services import (
    AquariumService,
    NotFoundError,
    ParameterService,
    RecordService,
    ValidationError,
)


@pytest.fixture
def services(
    tmp_path: Path,
) -> Generator[tuple[AquariumService, ParameterService, RecordService], None, None]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    yield (
        AquariumService(session_factory),
        ParameterService(session_factory),
        RecordService(session_factory),
    )
    engine.dispose()


def make_test_image() -> bytes:
    output = BytesIO()
    Image.new("RGB", (960, 640), color=(60, 120, 110)).save(output, format="PNG")
    return output.getvalue()


def test_aquarium_validation_and_archiving(services) -> None:
    aquariums, _, _ = services
    aquarium = aquariums.create_aquarium("  Rio  ", 120, "  Salon  ")

    assert aquarium.name == "Rio"
    assert aquarium.description == "Salon"
    assert [item.name for item in aquariums.list_aquariums(active_only=True)] == ["Rio"]

    aquariums.set_active(aquarium.id, False)

    assert aquariums.list_aquariums(active_only=True) == []
    assert aquariums.list_aquariums()[0].active is False


def test_aquarium_thumbnail_is_saved_preserved_and_removed(services) -> None:
    aquariums, _, _ = services
    aquarium = aquariums.create_aquarium("Reef", 120, None, make_test_image())
    saved_thumbnail = aquarium.thumbnail_data

    assert saved_thumbnail is not None
    with Image.open(BytesIO(saved_thumbnail)) as thumbnail:
        assert thumbnail.format == "JPEG"
        assert thumbnail.size == (480, 320)

    updated = aquariums.update_aquarium(aquarium.id, "Reef tank", 125, None)
    assert updated.thumbnail_data == saved_thumbnail

    removed = aquariums.update_aquarium(
        aquarium.id,
        "Reef tank",
        125,
        None,
        clear_thumbnail=True,
    )
    assert removed.thumbnail_data is None


def test_aquarium_rejects_invalid_thumbnail(services) -> None:
    aquariums, _, _ = services

    with pytest.raises(ValidationError, match="Could not read a valid image"):
        aquariums.create_aquarium("Reef", 120, None, b"not an image")


def test_measurement_keeps_timezone_and_optional_parameters(services) -> None:
    aquariums, parameters, records = services
    aquarium = aquariums.create_aquarium("Nano", 35, None)
    nitrate = parameters.create_parameter("NO3", "mg/l", None)
    phosphate = parameters.create_parameter("PO4", "mg/l", None)
    measured_at = datetime(2026, 10, 30, 12, 0, tzinfo=timezone(timedelta(hours=2)))

    records.record_measurement(
        aquarium.id,
        measured_at,
        nitrate.id,
        12.5,
        None,
    )

    [measurement] = records.measurements(aquarium.id)
    assert measurement.timestamp == datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc)
    assert measurement.parameter.name == "NO3"
    assert phosphate.id != nitrate.id


def test_measurement_can_be_edited_and_moved_to_another_day(services) -> None:
    aquariums, parameters, records = services
    aquarium = aquariums.create_aquarium("Nano", 35, None)
    ph = parameters.create_parameter("pH", "—", None)
    nitrate = parameters.create_parameter("NO3", "mg/l", None)
    original_timestamp = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    updated_timestamp = datetime(2026, 10, 30, 10, 30, tzinfo=timezone.utc)
    records.record_measurement(aquarium.id, original_timestamp, ph.id, 6.8, None)
    [original_measurement] = records.measurements(aquarium.id)
    loaded_measurement = records.get_measurement(aquarium.id, original_measurement.id)
    assert loaded_measurement.timestamp == original_timestamp
    assert loaded_measurement.parameter.name == "pH"

    records.update_measurement(
        aquarium.id,
        original_measurement.id,
        updated_timestamp,
        nitrate.id,
        12.5,
        " Retested ",
    )

    [updated_measurement] = records.measurements(aquarium.id)
    assert updated_measurement.timestamp == updated_timestamp
    assert updated_measurement.id == original_measurement.id
    assert updated_measurement.parameter_id == nitrate.id
    assert updated_measurement.value == 12.5
    assert updated_measurement.note == "Retested"
    [daily_history] = records.daily_history(aquarium.id)
    assert daily_history.day.isoformat() == "2026-10-30"
    assert daily_history.measurements[nitrate.id][0].id == original_measurement.id


def test_measurement_edit_is_scoped_to_its_aquarium(services) -> None:
    aquariums, parameters, records = services
    aquarium = aquariums.create_aquarium("Nano", 35, None)
    other_aquarium = aquariums.create_aquarium("Other", 40, None)
    ph = parameters.create_parameter("pH", "—", None)
    timestamp = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    records.record_measurement(aquarium.id, timestamp, ph.id, 6.8, None)
    [measurement] = records.measurements(aquarium.id)

    with pytest.raises(NotFoundError):
        records.get_measurement(other_aquarium.id, measurement.id)

    with pytest.raises(NotFoundError):
        records.update_measurement(
            other_aquarium.id,
            measurement.id,
            timestamp,
            ph.id,
            7.2,
            None,
        )

    [unchanged_measurement] = records.measurements(aquarium.id)
    assert unchanged_measurement.value == 6.8


def test_measured_parameters_are_scoped_and_ordered_by_latest_measurement(services) -> None:
    aquariums, parameters, records = services
    aquarium = aquariums.create_aquarium("Nano", 35, None)
    other_aquarium = aquariums.create_aquarium("Other", 40, None)
    nitrate = parameters.create_parameter("NO3", "mg/L", None)
    phosphate = parameters.create_parameter("PO4", "mg/L", None)
    unused = parameters.create_parameter("K", "mg/L", None)
    start = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    later = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
    records.record_measurement(aquarium.id, start, nitrate.id, 5, None)
    records.record_measurement(aquarium.id, later, phosphate.id, 0.2, None)
    records.record_measurement(other_aquarium.id, later, unused.id, 3, None)

    measured = records.measured_parameters(aquarium.id)

    assert [parameter.name for parameter in measured] == ["PO4", "NO3"]


def test_measurements_in_range_are_sorted_and_include_both_boundaries(services) -> None:
    aquariums, parameters, records = services
    aquarium = aquariums.create_aquarium("Nano", 35, None)
    other_aquarium = aquariums.create_aquarium("Other", 40, None)
    nitrate = parameters.create_parameter("NO3", "mg/L", None)
    phosphate = parameters.create_parameter("PO4", "mg/L", None)
    start = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    middle = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    records.record_measurement(
        aquarium.id,
        start - timedelta(seconds=1),
        nitrate.id,
        1,
        None,
    )
    records.record_measurement(aquarium.id, end, nitrate.id, 3, None)
    records.record_measurement(aquarium.id, middle, phosphate.id, 0.2, None)
    records.record_measurement(aquarium.id, middle, nitrate.id, 2, None)
    records.record_measurement(other_aquarium.id, middle, nitrate.id, 99, None)

    measurements = records.measurements_in_range(
        aquarium.id,
        nitrate.id,
        start,
        end,
    )

    assert [measurement.value for measurement in measurements] == [2, 3]
    assert [measurement.timestamp for measurement in measurements] == [middle, end]


def test_measurements_in_range_rejects_reversed_bounds(services) -> None:
    aquariums, parameters, records = services
    aquarium = aquariums.create_aquarium("Nano", 35, None)
    nitrate = parameters.create_parameter("NO3", "mg/L", None)

    with pytest.raises(ValidationError, match="Start date must not be after end date"):
        records.measurements_in_range(
            aquarium.id,
            nitrate.id,
            datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
        )


def test_notes_and_water_changes_are_saved_separately(services) -> None:
    aquariums, _, records = services
    aquarium = aquariums.create_aquarium("Community", 180, None)
    timestamp = datetime.now(timezone.utc)

    records.add_note(aquarium.id, timestamp, "Obserwacja", "Rośliny wypuszczają nowe liście.")
    records.add_water_change(aquarium.id, timestamp, WaterSource.MIXED, 45, "Mieszanka RO i kranu")

    [note] = records.notes(aquarium.id)
    [water_change] = records.water_changes(aquarium.id)
    assert note.category == "Obserwacja"
    assert note.content.startswith("Rośliny")
    assert water_change.source is WaterSource.MIXED
    assert water_change.volume_liters == 45


def test_note_can_be_edited_and_moved_to_another_day(services) -> None:
    aquariums, _, records = services
    aquarium = aquariums.create_aquarium("Community", 180, None)
    original_timestamp = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    updated_timestamp = datetime(2026, 10, 30, 14, 30, tzinfo=timezone.utc)
    records.add_note(aquarium.id, original_timestamp, "Observation", "Original content")
    [original_note] = records.notes(aquarium.id)
    assert records.get_note(aquarium.id, original_note.id).content == "Original content"

    records.update_note(
        aquarium.id,
        original_note.id,
        updated_timestamp,
        " Follow-up ",
        " Updated content ",
    )

    [updated_note] = records.notes(aquarium.id)
    assert updated_note.id == original_note.id
    assert updated_note.timestamp == updated_timestamp
    assert updated_note.category == "Follow-up"
    assert updated_note.content == "Updated content"
    [daily_history] = records.daily_history(aquarium.id)
    assert daily_history.day.isoformat() == "2026-10-30"
    assert daily_history.notes[0].id == original_note.id


def test_note_edit_is_scoped_to_its_aquarium(services) -> None:
    aquariums, _, records = services
    aquarium = aquariums.create_aquarium("Community", 180, None)
    other_aquarium = aquariums.create_aquarium("Other", 40, None)
    timestamp = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    records.add_note(aquarium.id, timestamp, None, "Original content")
    [note] = records.notes(aquarium.id)

    with pytest.raises(NotFoundError):
        records.get_note(other_aquarium.id, note.id)

    with pytest.raises(NotFoundError):
        records.update_note(other_aquarium.id, note.id, timestamp, None, "Changed")

    [unchanged_note] = records.notes(aquarium.id)
    assert unchanged_note.content == "Original content"


def test_water_change_can_be_edited_and_moved_to_another_day(services) -> None:
    aquariums, _, records = services
    aquarium = aquariums.create_aquarium("Community", 180, None)
    original_timestamp = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    updated_timestamp = datetime(2026, 10, 30, 14, 30, tzinfo=timezone.utc)
    records.add_water_change(aquarium.id, original_timestamp, WaterSource.RO, 15, "Original")
    [original_change] = records.water_changes(aquarium.id)
    assert records.get_water_change(aquarium.id, original_change.id).source is WaterSource.RO

    records.update_water_change(
        aquarium.id,
        original_change.id,
        updated_timestamp,
        WaterSource.MIXED,
        25,
        " Updated ",
    )

    [updated_change] = records.water_changes(aquarium.id)
    assert updated_change.id == original_change.id
    assert updated_change.timestamp == updated_timestamp
    assert updated_change.source is WaterSource.MIXED
    assert updated_change.volume_liters == 25
    assert updated_change.description == "Updated"
    [daily_history] = records.daily_history(aquarium.id)
    assert daily_history.day.isoformat() == "2026-10-30"
    assert daily_history.water_changes[0].id == original_change.id


def test_water_change_edit_is_scoped_to_its_aquarium(services) -> None:
    aquariums, _, records = services
    aquarium = aquariums.create_aquarium("Community", 180, None)
    other_aquarium = aquariums.create_aquarium("Other", 40, None)
    timestamp = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    records.add_water_change(aquarium.id, timestamp, WaterSource.RO, 15, None)
    [water_change] = records.water_changes(aquarium.id)

    with pytest.raises(NotFoundError):
        records.get_water_change(other_aquarium.id, water_change.id)

    with pytest.raises(NotFoundError):
        records.update_water_change(
            other_aquarium.id,
            water_change.id,
            timestamp,
            WaterSource.MIXED,
            25,
            None,
        )

    [unchanged_change] = records.water_changes(aquarium.id)
    assert unchanged_change.source is WaterSource.RO
    assert unchanged_change.volume_liters == 15


def test_daily_history_groups_same_day_records_and_keeps_all_entries(services) -> None:
    aquariums, parameters, records = services
    aquarium = aquariums.create_aquarium("Daily", 80, None)
    ph = parameters.create_parameter("pH", "—", None)
    timestamp = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)

    records.record_measurement(aquarium.id, timestamp, ph.id, 6.8, None)
    records.record_measurement(
        aquarium.id,
        timestamp + timedelta(hours=2),
        ph.id,
        7.1,
        None,
    )
    records.add_note(aquarium.id, timestamp, None, "First note for the day.")
    records.add_note(
        aquarium.id,
        timestamp + timedelta(hours=3),
        None,
        "Second note for the day.",
    )
    records.add_water_change(aquarium.id, timestamp, WaterSource.RO, 15, None)
    records.add_water_change(
        aquarium.id,
        timestamp + timedelta(hours=4),
        WaterSource.TAP,
        5,
        None,
    )

    [daily_history] = records.daily_history(aquarium.id)

    assert daily_history.measurements[ph.id]
    assert [measurement.value for measurement in daily_history.measurements[ph.id]] == [6.8, 7.1]
    assert [note.content for note in daily_history.notes] == [
        "First note for the day.",
        "Second note for the day.",
    ]
    assert [water_change.source for water_change in daily_history.water_changes] == [
        WaterSource.RO,
        WaterSource.TAP,
    ]


def test_rejects_invalid_values_and_naive_datetimes(services) -> None:
    aquariums, parameters, records = services
    with pytest.raises(ValidationError):
        aquariums.create_aquarium(" ", 40, None)
    with pytest.raises(ValidationError):
        aquariums.create_aquarium("Bad volume", 0, None)

    with pytest.raises(ValidationError):
        parameters.create_parameter("pH", "", None)

    aquarium = aquariums.create_aquarium("Valid", 40, None)
    with pytest.raises(ValidationError):
        records.add_note(aquarium.id, datetime(2026, 1, 1), None, "Naive timestamp")
    with pytest.raises(ValidationError):
        records.add_water_change(
            aquarium.id,
            datetime.now(timezone.utc),
            WaterSource.RO,
            -1,
            None,
        )


def test_validation_errors_are_english(services) -> None:
    aquariums, _, records = services
    with pytest.raises(ValidationError, match="Aquarium name is required"):
        aquariums.create_aquarium(" ", 40, None)

    aquarium = aquariums.create_aquarium("Valid", 40, None)
    with pytest.raises(ValidationError, match="Date and time must include a time zone"):
        records.add_note(aquarium.id, datetime(2026, 1, 1), None, "Naive timestamp")


def test_alembic_upgrade_creates_initial_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "migrated.sqlite3"
    database_url = f"sqlite:///{database_path}"
    project_root = Path(__file__).resolve().parents[1]

    upgrade_database(database_url, project_root)

    engine = create_database_engine(database_url)
    table_names = set(inspect(engine).get_table_names())
    aquarium_columns = {column["name"] for column in inspect(engine).get_columns("aquariums")}
    engine.dispose()
    assert {
        "alembic_version",
        "aquariums",
        "parameters",
        "measurements",
        "notes",
        "water_changes",
        "fertilizers",
        "fertilizer_effects",
        "fertilizer_applications",
    } <= table_names
    assert "measurement_sessions" not in table_names
    measurement_columns = {column["name"] for column in inspect(engine).get_columns("measurements")}
    assert {"aquarium_id", "timestamp"} <= measurement_columns
    assert "session_id" not in measurement_columns
    assert "thumbnail_data" in aquarium_columns
