from types import SimpleNamespace

from aqman.ui.components.fertilizer_application_form import (
    FertilizerApplicationForm,
)


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
