import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session, sessionmaker

from aqman import repositories
from aqman.images import ImageValidationError, create_thumbnail
from aqman.logger import get_logger
from aqman.models import (
    Aquarium,
    Fertilizer,
    FertilizerApplication,
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
    fertilizer_applications: tuple[FertilizerApplication, ...]


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


class FertilizerService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_fertilizers(self) -> list[Fertilizer]:
        with self._session_factory() as session:
            return repositories.list_fertilizers(session)

    def get_fertilizer(self, fertilizer_id: int) -> Fertilizer:
        with self._session_factory() as session:
            fertilizer = repositories.get_fertilizer(session, fertilizer_id)
            if fertilizer is None:
                raise NotFoundError("Fertilizer not found.")
            return fertilizer

    def list_effect_parameters(self) -> list[Parameter]:
        with self._session_factory() as session:
            return [
                parameter
                for parameter in repositories.list_parameters(session)
                if parameter.unit.strip().casefold() in {"mg/l", "ppm"}
            ]

    def create_fertilizer(
        self,
        name: str,
        dose_ml_per_100l: float,
        effects: Sequence[tuple[int, float]],
    ) -> Fertilizer:
        clean_name = _required_text(name, "Fertilizer name", 120)
        dose = _positive_number(dose_ml_per_100l, "Base dose")
        with self._session_factory.begin() as session:
            self._validate_unique_name(session, clean_name)
            clean_effects = self._validate_effects(session, effects)
            fertilizer = repositories.add_fertilizer(
                session,
                name=clean_name,
                dose_ml_per_100l=dose,
                effects=clean_effects,
            )
            loaded_fertilizer = repositories.get_fertilizer(session, fertilizer.id)
            assert loaded_fertilizer is not None
            fertilizer = loaded_fertilizer
        logger.info("Created fertilizer id=%s", fertilizer.id)
        return fertilizer

    def update_fertilizer(
        self,
        fertilizer_id: int,
        name: str,
        dose_ml_per_100l: float,
        effects: Sequence[tuple[int, float]],
    ) -> Fertilizer:
        clean_name = _required_text(name, "Fertilizer name", 120)
        dose = _positive_number(dose_ml_per_100l, "Base dose")
        with self._session_factory.begin() as session:
            fertilizer = repositories.get_fertilizer(session, fertilizer_id)
            if fertilizer is None:
                raise NotFoundError("Fertilizer not found.")
            self._validate_unique_name(session, clean_name, exclude_id=fertilizer_id)
            clean_effects = self._validate_effects(session, effects)
            fertilizer = repositories.update_fertilizer(
                session,
                fertilizer,
                name=clean_name,
                dose_ml_per_100l=dose,
                effects=clean_effects,
            )
            loaded_fertilizer = repositories.get_fertilizer(session, fertilizer.id)
            assert loaded_fertilizer is not None
            fertilizer = loaded_fertilizer
        logger.info("Updated fertilizer id=%s", fertilizer_id)
        return fertilizer

    def delete_fertilizer(self, fertilizer_id: int) -> None:
        with self._session_factory.begin() as session:
            fertilizer = repositories.get_fertilizer(session, fertilizer_id)
            if fertilizer is None:
                raise NotFoundError("Fertilizer not found.")
            if repositories.fertilizer_has_applications(session, fertilizer_id):
                raise ValidationError("Fertilizer has application history.")
            session.delete(fertilizer)
        logger.info("Deleted fertilizer id=%s", fertilizer_id)

    def _validate_unique_name(
        self,
        session: Session,
        name: str,
        *,
        exclude_id: int | None = None,
    ) -> None:
        normalized_name = name.casefold()
        if any(
            fertilizer_id != exclude_id
            and existing_name.casefold() == normalized_name
            for fertilizer_id, existing_name in repositories.list_fertilizer_names(session)
        ):
            raise ValidationError("A fertilizer with this name already exists.")

    def _validate_effects(
        self,
        session: Session,
        effects: Sequence[tuple[int, float]],
    ) -> list[tuple[int, float]]:
        if not effects:
            raise ValidationError("At least one fertilizer effect is required.")

        normalized_effects: list[tuple[int, float]] = []
        seen_parameter_ids: set[int] = set()
        for parameter_id, ppm_per_dose in effects:
            if not isinstance(parameter_id, int) or isinstance(parameter_id, bool):
                raise ValidationError("Select a water parameter for every fertilizer effect.")
            if parameter_id <= 0:
                raise ValidationError("Select a valid water parameter for every fertilizer effect.")
            if parameter_id in seen_parameter_ids:
                raise ValidationError("A fertilizer cannot have duplicate effects.")
            seen_parameter_ids.add(parameter_id)
            normalized_effects.append(
                (parameter_id, _positive_number(ppm_per_dose, "Fertilizer effect"))
            )

        parameters = repositories.get_parameters_by_ids(session, seen_parameter_ids)
        parameters_by_id = {parameter.id: parameter for parameter in parameters}
        if len(parameters_by_id) != len(seen_parameter_ids):
            raise ValidationError("A selected water parameter was not found.")

        seen_compounds: set[str] = set()
        for parameter in parameters:
            if parameter.unit.strip().casefold() not in {"mg/l", "ppm"}:
                raise ValidationError("Fertilizer effects require a parameter in mg/L or ppm.")
            compound = parameter.name.strip().casefold()
            if compound in seen_compounds:
                raise ValidationError("A fertilizer cannot have multiple effects for the same compound.")
            seen_compounds.add(compound)

        return normalized_effects


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

    def measured_parameters(self, aquarium_id: int) -> list[Parameter]:
        with self._session_factory() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            return repositories.list_measured_parameters(session, aquarium_id)

    def measurements_in_range(
        self,
        aquarium_id: int,
        parameter_id: int,
        start: datetime,
        end: datetime,
    ) -> list[Measurement]:
        clean_start = _utc_datetime(start)
        clean_end = _utc_datetime(end)
        if clean_start > clean_end:
            raise ValidationError("Start date must not be after end date.")
        with self._session_factory() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            if repositories.get_parameter(session, parameter_id) is None:
                raise NotFoundError("Parameter not found.")
            return repositories.list_measurements_in_range(
                session,
                aquarium_id,
                parameter_id,
                clean_start,
                clean_end,
            )

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

            applications_by_day: dict[date, list[FertilizerApplication]] = {}
            for application in repositories.list_fertilizer_applications(
                session,
                aquarium_id,
            ):
                day = application.timestamp.astimezone().date()
                applications_by_day.setdefault(day, []).append(application)
            for applications in applications_by_day.values():
                applications.sort(key=lambda item: (item.timestamp, item.id))

            days = (
                measurements_by_day.keys()
                | water_changes_by_day.keys()
                | notes_by_day.keys()
                | applications_by_day.keys()
            )
            return [
                DailyAquariumHistory(
                    day=day,
                    measurements={
                        parameter_id: tuple(values)
                        for parameter_id, values in measurements_by_day.get(day, {}).items()
                    },
                    water_changes=tuple(water_changes_by_day.get(day, ())),
                    notes=tuple(notes_by_day.get(day, ())),
                    fertilizer_applications=tuple(applications_by_day.get(day, ())),
                )
                for day in sorted(days, reverse=True)
            ]

    def add_fertilizer_application(
        self,
        aquarium_id: int,
        timestamp: datetime,
        fertilizer_id: int,
        actual_dose_ml: float,
        notes: str | None,
    ) -> FertilizerApplication:
        clean_timestamp = _utc_datetime(timestamp)
        actual_dose = _positive_number(actual_dose_ml, "Actual fertilizer dose")
        clean_notes = _clean_optional_text(notes)
        if clean_notes is not None and len(clean_notes) > 10000:
            raise ValidationError("Fertilizer notes must be at most 10000 characters.")
        with self._session_factory.begin() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            if repositories.get_fertilizer(session, fertilizer_id) is None:
                raise NotFoundError("Selected fertilizer not found.")
            application = repositories.add_fertilizer_application(
                session,
                aquarium_id=aquarium_id,
                timestamp=clean_timestamp,
                fertilizer_id=fertilizer_id,
                actual_dose_ml=actual_dose,
                notes=clean_notes,
            )
            loaded_application = repositories.get_fertilizer_application(
                session,
                aquarium_id,
                application.id,
            )
            assert loaded_application is not None
            application = loaded_application
        logger.info(
            "Recorded fertilizer application id=%s aquarium_id=%s fertilizer_id=%s",
            application.id,
            aquarium_id,
            fertilizer_id,
        )
        return application

    def get_fertilizer_application(
        self,
        aquarium_id: int,
        application_id: int,
    ) -> FertilizerApplication:
        with self._session_factory() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            application = repositories.get_fertilizer_application(
                session,
                aquarium_id,
                application_id,
            )
            if application is None:
                raise NotFoundError("Fertilizer application not found.")
            return application

    def update_fertilizer_application(
        self,
        aquarium_id: int,
        application_id: int,
        timestamp: datetime,
        fertilizer_id: int,
        actual_dose_ml: float,
        notes: str | None,
    ) -> FertilizerApplication:
        clean_timestamp = _utc_datetime(timestamp)
        actual_dose = _positive_number(actual_dose_ml, "Actual fertilizer dose")
        clean_notes = _clean_optional_text(notes)
        if clean_notes is not None and len(clean_notes) > 10000:
            raise ValidationError("Fertilizer notes must be at most 10000 characters.")
        with self._session_factory.begin() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            application = repositories.get_fertilizer_application(
                session,
                aquarium_id,
                application_id,
            )
            if application is None:
                raise NotFoundError("Fertilizer application not found.")
            fertilizer = repositories.get_fertilizer(session, fertilizer_id)
            if fertilizer is None:
                raise NotFoundError("Selected fertilizer not found.")
            application.timestamp = clean_timestamp
            application.fertilizer = fertilizer
            application.actual_dose_ml = actual_dose
            application.notes = clean_notes
            session.flush()
            loaded_application = repositories.get_fertilizer_application(
                session,
                aquarium_id,
                application_id,
            )
            assert loaded_application is not None
            application = loaded_application
        logger.info(
            "Updated fertilizer application id=%s aquarium_id=%s fertilizer_id=%s",
            application_id,
            aquarium_id,
            fertilizer_id,
        )
        return application

    def delete_fertilizer_application(self, aquarium_id: int, application_id: int) -> None:
        with self._session_factory.begin() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            application = repositories.get_fertilizer_application(
                session,
                aquarium_id,
                application_id,
            )
            if application is None:
                raise NotFoundError("Fertilizer application not found.")
            repositories.delete_fertilizer_application(session, application)
        logger.info(
            "Deleted fertilizer application id=%s aquarium_id=%s",
            application_id,
            aquarium_id,
        )

    def fertilizer_applications(self, aquarium_id: int) -> list[FertilizerApplication]:
        with self._session_factory() as session:
            if repositories.get_aquarium(session, aquarium_id) is None:
                raise NotFoundError("Aquarium not found.")
            return repositories.list_fertilizer_applications(session, aquarium_id)

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
