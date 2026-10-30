import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session, sessionmaker

from aqman import repositories
from aqman.images import ImageValidationError, create_thumbnail
from aqman.logger import get_logger
from aqman.models import (
    Aquarium,
    Measurement,
    Note,
    Parameter,
    WaterChange,
    WaterSource,
)

logger = get_logger(__name__)


class ValidationError(ValueError):
    pass


class NotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class DashboardAquarium:
    aquarium: Aquarium
    last_measurement_at: datetime | None


@dataclass(frozen=True)
class DailyAquariumHistory:
    day: date
    measurements: dict[int, tuple[Measurement, ...]]
    water_changes: tuple[WaterChange, ...]
    notes: tuple[Note, ...]


def _clean_optional_text(value: str | None) -> str | None:
    cleaned = value.strip() if value is not None else ""
    return cleaned or None


def _required_text(value: str, label: str, maximum: int) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(f"{label} is required.")
    if len(cleaned) > maximum:
        raise ValidationError(f"{label} must be at most {maximum} characters.")
    return cleaned


def _positive_number(value: float, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValidationError(f"{label} must be a number.") from error
    if not math.isfinite(number) or number <= 0:
        raise ValidationError(f"{label} must be greater than zero.")
    return number


def _finite_number(value: float, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValidationError(f"{label} must be a number.") from error
    if not math.isfinite(number):
        raise ValidationError(f"{label} must be a finite number.")
    return number


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError("Date and time must include a time zone.")
    return value.astimezone(timezone.utc)


def _aquarium_thumbnail(data: bytes | None) -> bytes | None:
    if data is None:
        return None
    try:
        return create_thumbnail(data)
    except ImageValidationError as error:
        raise ValidationError(str(error)) from error


class AquariumService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_aquariums(self, *, active_only: bool = False) -> list[Aquarium]:
        with self._session_factory() as session:
            return repositories.list_aquariums(session, active_only=active_only)

    def dashboard(self) -> list[DashboardAquarium]:
        with self._session_factory() as session:
            rows = repositories.list_dashboard_aquariums(session)
            return [
                DashboardAquarium(aquarium=aquarium, last_measurement_at=timestamp)
                for aquarium, timestamp in rows
            ]

    def create_aquarium(
        self,
        name: str,
        volume_liters: float,
        description: str | None,
        thumbnail_data: bytes | None = None,
    ) -> Aquarium:
        clean_name = _required_text(name, "Aquarium name", 120)
        volume = _positive_number(volume_liters, "Aquarium volume")
        clean_description = _clean_optional_text(description)
        thumbnail = _aquarium_thumbnail(thumbnail_data)
        with self._session_factory.begin() as session:
            aquarium = repositories.add_aquarium(
                session,
                name=clean_name,
                volume_liters=volume,
                description=clean_description,
                thumbnail_data=thumbnail,
            )
        logger.info("Created aquarium id=%s", aquarium.id)
        return aquarium

    def update_aquarium(
        self,
        aquarium_id: int,
        name: str,
        volume_liters: float,
        description: str | None,
        thumbnail_data: bytes | None = None,
        clear_thumbnail: bool = False,
    ) -> Aquarium:
        clean_name = _required_text(name, "Aquarium name", 120)
        volume = _positive_number(volume_liters, "Aquarium volume")
        clean_description = _clean_optional_text(description)
        thumbnail = _aquarium_thumbnail(thumbnail_data)
        with self._session_factory.begin() as session:
            aquarium = repositories.get_aquarium(session, aquarium_id)
            if aquarium is None:
                raise NotFoundError("Aquarium not found.")
            aquarium.name = clean_name
            aquarium.volume_liters = volume
            aquarium.description = clean_description
            if thumbnail is not None:
                aquarium.thumbnail_data = thumbnail
            elif clear_thumbnail:
                aquarium.thumbnail_data = None
            session.flush()
        logger.info("Updated aquarium id=%s", aquarium_id)
        return aquarium

    def set_active(self, aquarium_id: int, active: bool) -> Aquarium:
        with self._session_factory.begin() as session:
            aquarium = repositories.get_aquarium(session, aquarium_id)
            if aquarium is None:
                raise NotFoundError("Aquarium not found.")
            aquarium.active = active
        logger.info("Updated aquarium id=%s active=%s", aquarium_id, active)
        return aquarium


class ParameterService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_parameters(self) -> list[Parameter]:
        with self._session_factory() as session:
            return repositories.list_parameters(session)

    def create_parameter(self, name: str, unit: str, description: str | None) -> Parameter:
        clean_name = _required_text(name, "Parameter name", 80)
        clean_unit = _required_text(unit, "Unit", 30)
        clean_description = _clean_optional_text(description)
        with self._session_factory.begin() as session:
            parameter = repositories.add_parameter(
                session,
                name=clean_name,
                unit=clean_unit,
                description=clean_description,
            )
        logger.info("Created parameter id=%s", parameter.id)
        return parameter


class RecordService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_measurement(self, aquarium_id: int, measurement_id: int) -> Measurement:
        with self._session_factory() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            measurement = repositories.get_measurement(session, aquarium_id, measurement_id)
            if measurement is None:
                raise NotFoundError("Measurement not found.")
            return measurement

    def measurements(self, aquarium_id: int) -> list[Measurement]:
        with self._session_factory() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            return repositories.list_measurements(session, aquarium_id)

    def daily_history(self, aquarium_id: int) -> list[DailyAquariumHistory]:
        with self._session_factory() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")

            measurements_by_day: dict[date, dict[int, list[Measurement]]] = {}
            for measurement in sorted(
                repositories.list_measurements(session, aquarium_id),
                key=lambda item: (item.timestamp, item.id),
            ):
                day = measurement.timestamp.astimezone().date()
                measurements_by_day.setdefault(day, {}).setdefault(
                    measurement.parameter_id, []
                ).append(measurement)

            water_changes_by_day: dict[date, list[WaterChange]] = {}
            for water_change in repositories.list_water_changes(session, aquarium_id):
                day = water_change.timestamp.astimezone().date()
                water_changes_by_day.setdefault(day, []).append(water_change)
            for water_changes in water_changes_by_day.values():
                water_changes.sort(key=lambda item: (item.timestamp, item.id))

            notes_by_day: dict[date, list[Note]] = {}
            for note in repositories.list_notes(session, aquarium_id):
                day = note.timestamp.astimezone().date()
                notes_by_day.setdefault(day, []).append(note)
            for notes in notes_by_day.values():
                notes.sort(key=lambda item: (item.timestamp, item.id))

            days = measurements_by_day.keys() | water_changes_by_day.keys() | notes_by_day.keys()
            return [
                DailyAquariumHistory(
                    day=day,
                    measurements={
                        parameter_id: tuple(values)
                        for parameter_id, values in measurements_by_day.get(day, {}).items()
                    },
                    water_changes=tuple(water_changes_by_day.get(day, ())),
                    notes=tuple(notes_by_day.get(day, ())),
                )
                for day in sorted(days, reverse=True)
            ]

    def record_measurement(
        self,
        aquarium_id: int,
        timestamp: datetime,
        parameter_id: int,
        value: float,
        note: str | None,
    ) -> Measurement:
        clean_timestamp = _utc_datetime(timestamp)
        clean_value = _finite_number(value, "Measurement value")
        clean_note = _clean_optional_text(note)
        with self._session_factory.begin() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            if repositories.get_parameter(session, parameter_id) is None:
                raise NotFoundError("Selected parameter not found.")
            measurement = repositories.add_measurement(
                session,
                aquarium_id=aquarium_id,
                timestamp=clean_timestamp,
                parameter_id=parameter_id,
                value=clean_value,
                note=clean_note,
            )
        logger.info(
            "Recorded measurement id=%s aquarium_id=%s parameter_id=%s",
            measurement.id,
            aquarium_id,
            parameter_id,
        )
        return measurement

    def update_measurement(
        self,
        aquarium_id: int,
        measurement_id: int,
        timestamp: datetime,
        parameter_id: int,
        value: float,
        note: str | None,
    ) -> Measurement:
        clean_timestamp = _utc_datetime(timestamp)
        clean_value = _finite_number(value, "Measurement value")
        clean_note = _clean_optional_text(note)
        with self._session_factory.begin() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            measurement = repositories.get_measurement(session, aquarium_id, measurement_id)
            if measurement is None:
                raise NotFoundError("Measurement not found.")
            parameter = repositories.get_parameter(session, parameter_id)
            if parameter is None:
                raise NotFoundError("Selected parameter not found.")
            measurement.timestamp = clean_timestamp
            measurement.parameter = parameter
            measurement.value = clean_value
            measurement.note = clean_note
            session.flush()
        logger.info(
            "Updated measurement id=%s aquarium_id=%s parameter_id=%s",
            measurement_id,
            aquarium_id,
            parameter_id,
        )
        return measurement

    def add_note(
        self,
        aquarium_id: int,
        timestamp: datetime,
        category: str | None,
        content: str,
    ) -> Note:
        clean_timestamp = _utc_datetime(timestamp)
        clean_category = _clean_optional_text(category)
        clean_content = _required_text(content, "Note content", 10000)
        with self._session_factory.begin() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            note = repositories.add_note(
                session,
                aquarium_id=aquarium_id,
                timestamp=clean_timestamp,
                category=clean_category,
                content=clean_content,
            )
        logger.info("Added note id=%s aquarium_id=%s", note.id, aquarium_id)
        return note

    def get_note(self, aquarium_id: int, note_id: int) -> Note:
        with self._session_factory() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            note = repositories.get_note(session, aquarium_id, note_id)
            if note is None:
                raise NotFoundError("Note not found.")
            return note

    def update_note(
        self,
        aquarium_id: int,
        note_id: int,
        timestamp: datetime,
        category: str | None,
        content: str,
    ) -> Note:
        clean_timestamp = _utc_datetime(timestamp)
        clean_category = _clean_optional_text(category)
        clean_content = _required_text(content, "Note content", 10000)
        with self._session_factory.begin() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            note = repositories.get_note(session, aquarium_id, note_id)
            if note is None:
                raise NotFoundError("Note not found.")
            note.timestamp = clean_timestamp
            note.category = clean_category
            note.content = clean_content
            session.flush()
        logger.info("Updated note id=%s aquarium_id=%s", note_id, aquarium_id)
        return note

    def notes(self, aquarium_id: int) -> list[Note]:
        with self._session_factory() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            return repositories.list_notes(session, aquarium_id)

    def add_water_change(
        self,
        aquarium_id: int,
        timestamp: datetime,
        source: WaterSource,
        volume_liters: float,
        description: str | None,
    ) -> WaterChange:
        clean_timestamp = _utc_datetime(timestamp)
        volume = _positive_number(volume_liters, "Water-change volume")
        clean_description = _clean_optional_text(description)
        with self._session_factory.begin() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            water_change = repositories.add_water_change(
                session,
                aquarium_id=aquarium_id,
                timestamp=clean_timestamp,
                source=source,
                volume_liters=volume,
                description=clean_description,
            )
        logger.info(
            "Added water change id=%s aquarium_id=%s source=%s",
            water_change.id,
            aquarium_id,
            source.value,
        )
        return water_change

    def get_water_change(self, aquarium_id: int, water_change_id: int) -> WaterChange:
        with self._session_factory() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            water_change = repositories.get_water_change(session, aquarium_id, water_change_id)
            if water_change is None:
                raise NotFoundError("Water change not found.")
            return water_change

    def update_water_change(
        self,
        aquarium_id: int,
        water_change_id: int,
        timestamp: datetime,
        source: WaterSource,
        volume_liters: float,
        description: str | None,
    ) -> WaterChange:
        clean_timestamp = _utc_datetime(timestamp)
        volume = _positive_number(volume_liters, "Water-change volume")
        clean_description = _clean_optional_text(description)
        with self._session_factory.begin() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            water_change = repositories.get_water_change(
                session,
                aquarium_id,
                water_change_id,
            )
            if water_change is None:
                raise NotFoundError("Water change not found.")
            water_change.timestamp = clean_timestamp
            water_change.source = source
            water_change.volume_liters = volume
            water_change.description = clean_description
            session.flush()
        logger.info("Updated water change id=%s aquarium_id=%s", water_change_id, aquarium_id)
        return water_change

    def water_changes(self, aquarium_id: int) -> list[WaterChange]:
        with self._session_factory() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            return repositories.list_water_changes(session, aquarium_id)
