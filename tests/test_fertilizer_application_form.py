from types import SimpleNamespace

import pytest

from aqman.services import NotFoundError, ValidationError
from aqman.ui.components import fertilizer_application_form as form_module
from aqman.ui.components.fertilizer_application_form import (
    FertilizerApplicationForm,
)
from component_ui import install_datetime_picker, install_ui


def test_actual_dose_updates_target_effect_preview_without_changing_inputs() -> None:
    target_effect = SimpleNamespace(
        parameter_id=1,
        ppm_per_dose=10,
        parameter=SimpleNamespace(name="NO3"),
    )
    other_effect = SimpleNamespace(
        parameter_id=2,
        ppm_per_dose=1.5,
        parameter=SimpleNamespace(name="PO4"),
    )
    fertilizer = SimpleNamespace(
        id=7,
        dose_ml_per_100l=10,
        effects=[target_effect, other_effect],
    )
    aquarium = SimpleNamespace(id=3, volume_liters=180 / 0.85)
    form = FertilizerApplicationForm.__new__(FertilizerApplicationForm)
    form._language = "en"
    form._fertilizers = {fertilizer.id: fertilizer}
    form._fertilizer = SimpleNamespace(value=fertilizer.id)
    form._aquarium_id_provider = lambda: aquarium.id
    form._aquarium_service = SimpleNamespace(list_aquariums=lambda: [aquarium])
    form._target_parameter = SimpleNamespace(value=target_effect.parameter_id)
    form._target_increase = SimpleNamespace(value=5)
    form._actual_dose = SimpleNamespace(value=4.5)
    form._target_effect_preview = SimpleNamespace(text="")
    form._other_effects = SimpleNamespace(text="")

    form._refresh_effect_preview()

    assert form._target_effect_preview.text == "NO₃: +2.5 ppm"
    assert form._other_effects.text == "PO₄: +0.375 ppm"
    assert form._actual_dose.value == 4.5
    assert form._target_increase.value == 5

    form._actual_dose.value = 9
    form._refresh_effect_preview()

    assert form._target_effect_preview.text == "NO₃: +5 ppm"
    assert form._actual_dose.value == 9
    assert form._target_increase.value == 5

    form._actual_dose.value = None
    form._refresh_effect_preview()
    assert form._target_effect_preview.text == "—"
    assert form._other_effects.text == form._t("fertilizer_effects_unavailable")


def test_form_selects_fertilizers_and_exposes_valid_values(monkeypatch) -> None:
    fake_ui = install_ui(monkeypatch, form_module)
    install_datetime_picker(monkeypatch, form_module)
    parameter = SimpleNamespace(id=1, name="NO3", unit="mg/L")
    effect = SimpleNamespace(parameter_id=1, ppm_per_dose=10, parameter=parameter)
    fertilizer = SimpleNamespace(
        id=7,
        name="Nitrate",
        dose_ml_per_100l=10,
        effects=[effect],
    )
    aquarium = SimpleNamespace(id=3, volume_liters=100)
    service = SimpleNamespace(list_aquariums=lambda: [aquarium])
    saved = []
    form = FertilizerApplicationForm(service, lambda: 3, "en", saved.append)
    form.set_fertilizers([fertilizer])

    assert form._fertilizer.options == {7: "Nitrate"}
    assert form._fertilizer.value == 7
    assert form._target_parameter.options == {1: "NO3 (mg/L)"}
    assert form._target_parameter.value == 1
    assert form._actual_dose.value is not None
    form._notes.value = "After water change"
    values = form.values
    assert (values.fertilizer_id, values.actual_dose_ml, values.notes) == (
        7,
        form._actual_dose.value,
        "After water change",
    )
    fake_ui.by_label(form._t("save_fertilizer_application")).on_click()
    assert saved == [form]
    form.reset_after_save()
    assert form._notes.value == ""
    assert form._datetime.value.tzinfo is not None

    form.set_fertilizers([])
    assert form._fertilizer.options == {}
    assert form._fertilizer.value is None
    assert form._recommended_dose.text == form._t("fertilizer_dose_unavailable")
    assert form._actual_dose.value is None
    assert form._target_effect_preview.text == "—"
    assert form._other_effects.text == form._t("fertilizer_effects_unavailable")


@pytest.mark.parametrize(
    ("fertilizer_id", "dose", "message"),
    [
        (None, 5, "Select a fertilizer first."),
        ("bad", 5, "Select a fertilizer first."),
        (1, None, "Actual fertilizer dose must be a number."),
    ],
)
def test_values_reject_invalid_fertilizer_or_actual_dose(
    monkeypatch, fertilizer_id, dose, message
) -> None:
    install_ui(monkeypatch, form_module)
    install_datetime_picker(monkeypatch, form_module)
    form = FertilizerApplicationForm(
        SimpleNamespace(list_aquariums=lambda: []), lambda: 1, "en", lambda _: None
    )
    form._fertilizer.value = fertilizer_id
    form._actual_dose.value = dose

    with pytest.raises(ValidationError, match=message):
        form.values


def test_recommendation_falls_back_when_aquarium_is_unavailable(monkeypatch) -> None:
    install_ui(monkeypatch, form_module)
    install_datetime_picker(monkeypatch, form_module)
    parameter = SimpleNamespace(id=1, name="NO3", unit="mg/L")
    fertilizer = SimpleNamespace(
        id=7,
        dose_ml_per_100l=10,
        effects=[SimpleNamespace(parameter_id=1, ppm_per_dose=2, parameter=parameter)],
    )
    form = FertilizerApplicationForm(
        SimpleNamespace(list_aquariums=lambda: []), lambda: 99, "en", lambda _: None
    )
    form._fertilizers = {7: fertilizer}
    form._fertilizer.value = 7
    form._target_parameter.value = 1

    form._refresh_recommendation()

    assert form._recommended_dose.text == form._t("fertilizer_dose_unavailable")
    assert form._actual_dose.value is None
    assert form._other_effects.text == form._t("fertilizer_effects_unavailable")
    with pytest.raises(NotFoundError):
        form._current_aquarium()
