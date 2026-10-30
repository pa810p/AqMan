from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from aqman.models import (
    Aquarium,
    Measurement,
    MeasurementSession,
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
    latest_sessions = (
        select(
            MeasurementSession.aquarium_id,
            func.max(MeasurementSession.timestamp).label("last_measurement_at"),
        )
        .group_by(MeasurementSession.aquarium_id)
        .subquery()
    )
    statement = (
        select(Aquarium, latest_sessions.c.last_measurement_at)
        .outerjoin(latest_sessions, latest_sessions.c.aquarium_id == Aquarium.id)
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


def add_measurement_session(
    session: Session,
    *,
    aquarium_id: int,
    timestamp: datetime,
    general_note: str | None,
    values: dict[int, tuple[float, str | None]],
) -> MeasurementSession:
    measurement_session = MeasurementSession(
        aquarium_id=aquarium_id,
        timestamp=timestamp,
        general_note=general_note,
    )
    session.add(measurement_session)
    session.flush()
    for parameter_id, (value, note) in values.items():
        session.add(
            Measurement(
                session_id=measurement_session.id,
                parameter_id=parameter_id,
                value=value,
                note=note,
            )
        )
    return measurement_session


def get_measurement(
    session: Session,
    aquarium_id: int,
    measurement_id: int,
) -> Measurement | None:
    statement = (
        select(Measurement)
        .join(MeasurementSession)
        .where(
            Measurement.id == measurement_id,
            MeasurementSession.aquarium_id == aquarium_id,
        )
        .options(
            selectinload(Measurement.parameter),
            selectinload(Measurement.session),
        )
    )
    return session.scalar(statement)


def list_measurement_sessions(session: Session, aquarium_id: int) -> list[MeasurementSession]:
    statement = (
        select(MeasurementSession)
        .where(MeasurementSession.aquarium_id == aquarium_id)
        .options(selectinload(MeasurementSession.measurements).selectinload(Measurement.parameter))
        .order_by(MeasurementSession.timestamp.desc(), MeasurementSession.id.desc())
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
