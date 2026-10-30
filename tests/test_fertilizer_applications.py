from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from aqman.database import Base, create_database_engine, create_session_factory
from aqman.services import (
    AquariumService,
    FertilizerService,
    NotFoundError,
    ParameterService,
    RecordService,
    ValidationError,
)


@pytest.fixture
def application_services(
    tmp_path: Path,
) -> Generator[
    tuple[AquariumService, FertilizerService, ParameterService, RecordService, sessionmaker[Session]],
    None,
    None,
]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'fertilizer-applications.sqlite3'}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    yield (
        AquariumService(session_factory),
        FertilizerService(session_factory),
        ParameterService(session_factory),
        RecordService(session_factory),
        session_factory,
    )
    engine.dispose()


def create_fertilizer(application_services):
    aquariums, fertilizers, parameters, _, _ = application_services
    aquarium = aquariums.create_aquarium("Test tank", 180, None)
    no3 = parameters.create_parameter("NO3", "mg/L", None)
    fertilizer = fertilizers.create_fertilizer("Nitro", 10, [(no3.id, 10)])
    return aquarium, fertilizer


def test_fertilizer_application_can_be_created_updated_and_deleted(application_services) -> None:
    aquariums, fertilizers, _, records, _ = application_services
    aquarium, fertilizer = create_fertilizer(application_services)
    timestamp = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)

    application = records.add_fertilizer_application(
        aquarium.id,
        timestamp,
        fertilizer.id,
        9,
        "  After pruning  ",
    )

    assert application.timestamp == timestamp
    assert application.actual_dose_ml == 9
    assert application.notes == "After pruning"
    assert application.fertilizer.name == "Nitro"
    [saved] = records.fertilizer_applications(aquarium.id)
    assert saved.id == application.id

    updated_timestamp = datetime(2026, 10, 31, 15, 30, tzinfo=timezone.utc)
    updated = records.update_fertilizer_application(
        aquarium.id,
        application.id,
        updated_timestamp,
        fertilizer.id,
        8.5,
        "Updated note",
    )

    assert updated.timestamp == updated_timestamp
    assert updated.actual_dose_ml == 8.5
    assert updated.notes == "Updated note"
    assert [entry.id for entry in records.fertilizer_applications(aquarium.id)] == [
        application.id
    ]

    records.delete_fertilizer_application(aquarium.id, application.id)

    assert records.fertilizer_applications(aquarium.id) == []
    fertilizers.delete_fertilizer(fertilizer.id)
    assert fertilizers.list_fertilizers() == []


def test_fertilizer_application_history_is_grouped_by_local_day(application_services) -> None:
    aquariums, _, _, records, _ = application_services
    aquarium, fertilizer = create_fertilizer(application_services)
    first_time = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    second_time = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)

    records.add_fertilizer_application(aquarium.id, first_time, fertilizer.id, 9, None)
    records.add_fertilizer_application(aquarium.id, second_time, fertilizer.id, 8.5, None)
    records.add_fertilizer_application(
        aquarium.id,
        second_time.replace(hour=14),
        fertilizer.id,
        8,
        "Second dose",
    )

    history = records.daily_history(aquarium.id)

    assert [day.day.isoformat() for day in history] == ["2026-10-30", "2026-10-29"]
    assert [entry.actual_dose_ml for entry in history[0].fertilizer_applications] == [
        8.5,
        8,
    ]
    assert history[1].fertilizer_applications[0].fertilizer.name == "Nitro"


def test_fertilizer_applications_are_scoped_and_protect_catalog_history(
    application_services,
) -> None:
    aquariums, fertilizers, _, records, _ = application_services
    aquarium, fertilizer = create_fertilizer(application_services)
    other_aquarium = aquariums.create_aquarium("Other tank", 50, None)
    timestamp = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    application = records.add_fertilizer_application(
        aquarium.id,
        timestamp,
        fertilizer.id,
        9,
        None,
    )

    with pytest.raises(NotFoundError, match="Fertilizer application not found"):
        records.get_fertilizer_application(other_aquarium.id, application.id)
    with pytest.raises(NotFoundError, match="Fertilizer application not found"):
        records.update_fertilizer_application(
            other_aquarium.id,
            application.id,
            timestamp,
            fertilizer.id,
            8,
            None,
        )
    with pytest.raises(NotFoundError, match="Fertilizer application not found"):
        records.delete_fertilizer_application(other_aquarium.id, application.id)
    with pytest.raises(ValidationError, match="has application history"):
        fertilizers.delete_fertilizer(fertilizer.id)

    assert records.get_fertilizer_application(aquarium.id, application.id).actual_dose_ml == 9
