from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from aqman.database import Base, create_database_engine, create_session_factory
from aqman.models import FertilizerEffect
from aqman.services import FertilizerService, ParameterService, NotFoundError, ValidationError


@pytest.fixture
def fertilizer_services(
    tmp_path: Path,
) -> Generator[tuple[FertilizerService, ParameterService, sessionmaker[Session]], None, None]:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'fertilizers.sqlite3'}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    yield (
        FertilizerService(session_factory),
        ParameterService(session_factory),
        session_factory,
    )
    engine.dispose()


def test_fertilizer_crud_and_effects(fertilizer_services) -> None:
    fertilizers, parameters, session_factory = fertilizer_services
    no3 = parameters.create_parameter("NO3", "mg/L", None)
    potassium = parameters.create_parameter("K", "ppm", None)
    parameters.create_parameter("pH", "pH", None)

    fertilizer = fertilizers.create_fertilizer(
        "  EasyLife Nitro  ",
        10,
        [(no3.id, 10), (potassium.id, 1.5)],
    )

    assert fertilizer.name == "EasyLife Nitro"
    assert fertilizer.dose_ml_per_100l == 10
    assert [
        (effect.parameter.name, effect.ppm_per_dose)
        for effect in fertilizer.effects
    ] == [("NO3", 10), ("K", 1.5)]
    assert [parameter.name for parameter in fertilizers.list_effect_parameters()] == [
        "K",
        "NO3",
    ]

    updated = fertilizers.update_fertilizer(
        fertilizer.id,
        "EasyLife Nitro Plus",
        12,
        [(potassium.id, 2.5)],
    )

    assert updated.name == "EasyLife Nitro Plus"
    assert updated.dose_ml_per_100l == 12
    assert [(effect.parameter.name, effect.ppm_per_dose) for effect in updated.effects] == [
        ("K", 2.5)
    ]

    fertilizers.delete_fertilizer(fertilizer.id)

    assert fertilizers.list_fertilizers() == []
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(FertilizerEffect)) == 0
    with pytest.raises(NotFoundError, match="Fertilizer not found"):
        fertilizers.get_fertilizer(fertilizer.id)


def test_parameter_with_fertilizer_effect_cannot_be_deleted(fertilizer_services) -> None:
    fertilizers, parameters, _ = fertilizer_services
    no3 = parameters.create_parameter("NO3", "mg/L", None)
    fertilizers.create_fertilizer("Nitro", 10, [(no3.id, 5)])

    with pytest.raises(ValidationError, match="fertilizer effects"):
        parameters.delete_parameter(no3.id)

    assert [parameter.id for parameter in parameters.list_parameters()] == [no3.id]


def test_fertilizer_names_are_unique_case_insensitively(fertilizer_services) -> None:
    fertilizers, parameters, _ = fertilizer_services
    no3 = parameters.create_parameter("NO3", "ppm", None)
    fertilizers.create_fertilizer("EasyLife Nitro", 10, [(no3.id, 5)])

    with pytest.raises(ValidationError, match="name already exists"):
        fertilizers.create_fertilizer("  easylife NITRO ", 12, [(no3.id, 6)])


def test_fertilizer_effects_require_supported_unique_compounds(fertilizer_services) -> None:
    fertilizers, parameters, _ = fertilizer_services
    no3_mg = parameters.create_parameter("NO3", "mg/L", None)
    no3_ppm = parameters.create_parameter("no3", "ppm", None)
    ph = parameters.create_parameter("pH", "pH", None)

    with pytest.raises(ValidationError, match="multiple effects for the same compound"):
        fertilizers.create_fertilizer(
            "Nitro",
            10,
            [(no3_mg.id, 5), (no3_ppm.id, 5)],
        )
    with pytest.raises(ValidationError, match="require a parameter in mg/L or ppm"):
        fertilizers.create_fertilizer("pH fertilizer", 10, [(ph.id, 1)])
    with pytest.raises(ValidationError, match="duplicate effects"):
        fertilizers.create_fertilizer("Repeated", 10, [(no3_mg.id, 5), (no3_mg.id, 6)])
    with pytest.raises(ValidationError, match="At least one fertilizer effect"):
        fertilizers.create_fertilizer("No effects", 10, [])


@pytest.mark.parametrize(
    ("dose", "effect"),
    [(0, 1), (-1, 1), (10, 0), (10, float("nan")), (float("inf"), 1)],
)
def test_fertilizer_rejects_non_positive_or_non_finite_values(
    fertilizer_services,
    dose: float,
    effect: float,
) -> None:
    fertilizers, parameters, _ = fertilizer_services
    no3 = parameters.create_parameter("NO3", "ppm", None)

    with pytest.raises(ValidationError):
        fertilizers.create_fertilizer("Invalid", dose, [(no3.id, effect)])
