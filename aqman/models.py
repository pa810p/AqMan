from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.engine import Dialect
from sqlalchemy.types import DateTime, TypeDecorator

from aqman.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Datetime values must include a timezone.")
        value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if dialect.name == "sqlite":
            return value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None:
            raise ValueError("Database returned a datetime without timezone information.")
        return value.astimezone(timezone.utc)


class WaterSource(str, Enum):
    RO = "RO"
    TAP = "kran"
    MIXED = "mieszane"


class Aquarium(Base):
    __tablename__ = "aquariums"
    __table_args__ = (
        CheckConstraint("volume_liters > 0", name="ck_aquariums_volume_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    volume_liters: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_data: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="aquarium", cascade="all, delete-orphan"
    )
    notes: Mapped[list["Note"]] = relationship(back_populates="aquarium", cascade="all, delete-orphan")
    water_changes: Mapped[list["WaterChange"]] = relationship(
        back_populates="aquarium", cascade="all, delete-orphan"
    )
    fertilizer_applications: Mapped[list["FertilizerApplication"]] = relationship(
        back_populates="aquarium",
        cascade="all, delete-orphan",
    )


class Parameter(Base):
    __tablename__ = "parameters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    measurements: Mapped[list["Measurement"]] = relationship(back_populates="parameter")
    fertilizer_effects: Mapped[list["FertilizerEffect"]] = relationship(
        back_populates="parameter"
    )


class Fertilizer(Base):
    __tablename__ = "fertilizers"
    __table_args__ = (
        CheckConstraint(
            "dose_ml_per_100l > 0",
            name="ck_fertilizers_dose_positive",
        ),
        Index("uq_fertilizers_name_lower", text("lower(name)"), unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    dose_ml_per_100l: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    effects: Mapped[list["FertilizerEffect"]] = relationship(
        back_populates="fertilizer",
        cascade="all, delete-orphan",
        order_by="FertilizerEffect.id",
    )


class FertilizerEffect(Base):
    __tablename__ = "fertilizer_effects"
    __table_args__ = (
        CheckConstraint("ppm_per_dose > 0", name="ck_fertilizer_effects_ppm_positive"),
        UniqueConstraint(
            "fertilizer_id",
            "parameter_id",
            name="uq_fertilizer_effects_fertilizer_parameter",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fertilizer_id: Mapped[int] = mapped_column(
        ForeignKey("fertilizers.id", ondelete="CASCADE"),
        nullable=False,
    )
    parameter_id: Mapped[int] = mapped_column(ForeignKey("parameters.id"), nullable=False)
    ppm_per_dose: Mapped[float] = mapped_column(Float, nullable=False)

    fertilizer: Mapped[Fertilizer] = relationship(back_populates="effects")
    parameter: Mapped[Parameter] = relationship(back_populates="fertilizer_effects")


class FertilizerApplication(Base):
    __tablename__ = "fertilizer_applications"
    __table_args__ = (
        CheckConstraint(
            "actual_dose_ml > 0",
            name="ck_fertilizer_applications_dose_positive",
        ),
        Index(
            "ix_fertilizer_applications_aquarium_timestamp",
            "aquarium_id",
            "timestamp",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    aquarium_id: Mapped[int] = mapped_column(
        ForeignKey("aquariums.id", ondelete="CASCADE"),
        nullable=False,
    )
    fertilizer_id: Mapped[int] = mapped_column(
        ForeignKey("fertilizers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actual_dose_ml: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    aquarium: Mapped[Aquarium] = relationship(back_populates="fertilizer_applications")
    fertilizer: Mapped[Fertilizer] = relationship()


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (Index("ix_measurements_aquarium_timestamp", "aquarium_id", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aquarium_id: Mapped[int] = mapped_column(
        ForeignKey("aquariums.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    parameter_id: Mapped[int] = mapped_column(ForeignKey("parameters.id"), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    aquarium: Mapped[Aquarium] = relationship(back_populates="measurements")
    parameter: Mapped[Parameter] = relationship(back_populates="measurements")


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_aquarium_timestamp", "aquarium_id", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aquarium_id: Mapped[int] = mapped_column(
        ForeignKey("aquariums.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    category: Mapped[str | None] = mapped_column(String(80))
    content: Mapped[str] = mapped_column(Text, nullable=False)

    aquarium: Mapped[Aquarium] = relationship(back_populates="notes")


class WaterChange(Base):
    __tablename__ = "water_changes"
    __table_args__ = (
        CheckConstraint("volume_liters > 0", name="ck_water_changes_volume_positive"),
        Index("ix_water_changes_aquarium_timestamp", "aquarium_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aquarium_id: Mapped[int] = mapped_column(
        ForeignKey("aquariums.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    source: Mapped[WaterSource] = mapped_column(
        SqlEnum(
            WaterSource,
            values_callable=lambda enum_type: [item.value for item in enum_type],
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="water_source",
        ),
        nullable=False,
    )
    volume_liters: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    aquarium: Mapped[Aquarium] = relationship(back_populates="water_changes")
