from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from aqman.models import (
    Aquarium,
    Fertilizer,
    FertilizerEffect,
    Measurement,
    Note,
    Parameter,
    WaterChange,
    WaterSource,
)


def list_aquariums(session: Session, *, active_only: bool = False) -> list[Aquarium]:
    statement = select(Aquarium).order_by(Aquarium.name, Aquarium.id)
    if active_only:
        statement = statement.where(Aquarium.active.is_(True))
    return list(session.scalars(statement))


def get_aquarium(session: Session, aquarium_id: int) -> Aquarium | None:
    return session.get(Aquarium, aquarium_id)


def add_aquarium(
    session: Session,
    *,
    name: str,
    volume_liters: float,
    description: str | None,
    thumbnail_data: bytes | None,
) -> Aquarium:
    aquarium = Aquarium(
        name=name,
        volume_liters=volume_liters,
        description=description,
        thumbnail_data=thumbnail_data,
    )
    session.add(aquarium)
    session.flush()
    return aquarium


def list_dashboard_aquariums(session: Session) -> list[tuple[Aquarium, datetime | None]]:
    latest_measurements = (
        select(
            Measurement.aquarium_id,
            func.max(Measurement.timestamp).label("last_measurement_at"),
        )
        .group_by(Measurement.aquarium_id)
        .subquery()
    )
    statement = (
        select(Aquarium, latest_measurements.c.last_measurement_at)
        .outerjoin(latest_measurements, latest_measurements.c.aquarium_id == Aquarium.id)
        .where(Aquarium.active.is_(True))
        .order_by(Aquarium.name, Aquarium.id)
    )
    return [(aquarium, timestamp) for aquarium, timestamp in session.execute(statement)]


def list_parameters(session: Session) -> list[Parameter]:
    return list(session.scalars(select(Parameter).order_by(Parameter.name, Parameter.unit, Parameter.id)))


def get_parameter(session: Session, parameter_id: int) -> Parameter | None:
    return session.get(Parameter, parameter_id)


def add_parameter(
    session: Session,
    *,
    name: str,
    unit: str,
    description: str | None,
) -> Parameter:
    parameter = Parameter(name=name, unit=unit, description=description)
    session.add(parameter)
    session.flush()
    return parameter


def list_fertilizer_names(session: Session) -> list[tuple[int, str]]:
    statement = select(Fertilizer.id, Fertilizer.name).order_by(Fertilizer.id)
    return [(fertilizer_id, name) for fertilizer_id, name in session.execute(statement)]


def list_fertilizers(session: Session) -> list[Fertilizer]:
    statement = (
        select(Fertilizer)
        .options(
            selectinload(Fertilizer.effects).selectinload(FertilizerEffect.parameter)
        )
        .order_by(Fertilizer.name, Fertilizer.id)
    )
    return list(session.scalars(statement))


def get_fertilizer(session: Session, fertilizer_id: int) -> Fertilizer | None:
    statement = (
        select(Fertilizer)
        .where(Fertilizer.id == fertilizer_id)
        .options(
            selectinload(Fertilizer.effects).selectinload(FertilizerEffect.parameter)
        )
    )
    return session.scalar(statement)


def get_parameters_by_ids(session: Session, parameter_ids: set[int]) -> list[Parameter]:
    if not parameter_ids:
        return []
    statement = select(Parameter).where(Parameter.id.in_(parameter_ids))
    return list(session.scalars(statement))


def add_fertilizer(
    session: Session,
    *,
    name: str,
    dose_ml_per_100l: float,
    effects: list[tuple[int, float]],
) -> Fertilizer:
    fertilizer = Fertilizer(
        name=name,
        dose_ml_per_100l=dose_ml_per_100l,
        effects=[
            FertilizerEffect(parameter_id=parameter_id, ppm_per_dose=ppm_per_dose)
            for parameter_id, ppm_per_dose in effects
        ],
    )
    session.add(fertilizer)
    session.flush()
    return fertilizer


def update_fertilizer(
    session: Session,
    fertilizer: Fertilizer,
    *,
    name: str,
    dose_ml_per_100l: float,
    effects: list[tuple[int, float]],
) -> Fertilizer:
    fertilizer.name = name
    fertilizer.dose_ml_per_100l = dose_ml_per_100l

    effects_by_parameter = {effect.parameter_id: effect for effect in fertilizer.effects}
    requested_parameter_ids = {parameter_id for parameter_id, _ in effects}
    for parameter_id, effect in effects_by_parameter.items():
        if parameter_id not in requested_parameter_ids:
            fertilizer.effects.remove(effect)

    for parameter_id, ppm_per_dose in effects:
        existing_effect = effects_by_parameter.get(parameter_id)
        if existing_effect is None:
            fertilizer.effects.append(
                FertilizerEffect(
                    parameter_id=parameter_id,
                    ppm_per_dose=ppm_per_dose,
                )
            )
        else:
            existing_effect.ppm_per_dose = ppm_per_dose

    session.flush()
    return fertilizer


def add_measurement(
    session: Session,
    *,
    aquarium_id: int,
    timestamp: datetime,
    parameter_id: int,
    value: float,
    note: str | None,
) -> Measurement:
    measurement = Measurement(
        aquarium_id=aquarium_id,
        timestamp=timestamp,
        parameter_id=parameter_id,
        value=value,
        note=note,
    )
    session.add(measurement)
    session.flush()
    return measurement


def get_measurement(
    session: Session,
    aquarium_id: int,
    measurement_id: int,
) -> Measurement | None:
    statement = (
        select(Measurement)
        .where(
            Measurement.id == measurement_id,
            Measurement.aquarium_id == aquarium_id,
        )
        .options(selectinload(Measurement.parameter))
    )
    return session.scalar(statement)


def list_measurements(session: Session, aquarium_id: int) -> list[Measurement]:
    statement = (
        select(Measurement)
        .where(Measurement.aquarium_id == aquarium_id)
        .options(selectinload(Measurement.parameter))
        .order_by(Measurement.timestamp.desc(), Measurement.id.desc())
    )
    return list(session.scalars(statement))


def add_note(
    session: Session,
    *,
    aquarium_id: int,
    timestamp: datetime,
    category: str | None,
    content: str,
) -> Note:
    note = Note(
        aquarium_id=aquarium_id,
        timestamp=timestamp,
        category=category,
        content=content,
    )
    session.add(note)
    session.flush()
    return note


def get_note(session: Session, aquarium_id: int, note_id: int) -> Note | None:
    statement = select(Note).where(Note.id == note_id, Note.aquarium_id == aquarium_id)
    return session.scalar(statement)


def list_notes(session: Session, aquarium_id: int) -> list[Note]:
    statement = (
        select(Note)
        .where(Note.aquarium_id == aquarium_id)
        .order_by(Note.timestamp.desc(), Note.id.desc())
    )
    return list(session.scalars(statement))


def add_water_change(
    session: Session,
    *,
    aquarium_id: int,
    timestamp: datetime,
    source: WaterSource,
    volume_liters: float,
    description: str | None,
) -> WaterChange:
    water_change = WaterChange(
        aquarium_id=aquarium_id,
        timestamp=timestamp,
        source=source,
        volume_liters=volume_liters,
        description=description,
    )
    session.add(water_change)
    session.flush()
    return water_change


def get_water_change(
    session: Session,
    aquarium_id: int,
    water_change_id: int,
) -> WaterChange | None:
    statement = select(WaterChange).where(
        WaterChange.id == water_change_id,
        WaterChange.aquarium_id == aquarium_id,
    )
    return session.scalar(statement)


def list_water_changes(session: Session, aquarium_id: int) -> list[WaterChange]:
    statement = (
        select(WaterChange)
        .where(WaterChange.aquarium_id == aquarium_id)
        .order_by(WaterChange.timestamp.desc(), WaterChange.id.desc())
    )
    return list(session.scalars(statement))
