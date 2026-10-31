from types import SimpleNamespace

import pytest

from aqman.services import ValidationError
from aqman.ui.components import measurement_form as measurement_form_module
from aqman.ui.components.measurement_form import MeasurementForm
from component_ui import install_datetime_picker, install_ui


def test_measurement_form_values_parameter_selection_and_reset(monkeypatch):
    fake_ui = install_ui(monkeypatch, measurement_form_module)
    install_datetime_picker(monkeypatch, measurement_form_module)
    saved = []
    form = MeasurementForm("en", saved.append, show_time=False)
    nitrate = SimpleNamespace(id=1, name="NO3", unit="mg/L")
    phosphate = SimpleNamespace(id=2, name="PO4", unit="mg/L")

    form.set_parameters([nitrate, phosphate])
    assert form._parameter.options == {1: "NO3 (mg/L)", 2: "PO4 (mg/L)"}
    assert form._parameter.value == 1
    assert form._parameter.updated == 1
    form._parameter.value = "2"
    form.set_parameters([nitrate, phosphate])
    assert form._parameter.value == 2
    form.set_parameters([nitrate])
    assert form._parameter.value == 1

    form._parameter.value = "1"
    form._value.value = "4.25"
    form._note.value = "after feeding"
    values = form.values
    assert (values.parameter_id, values.value, values.note) == (
        1,
        4.25,
        "after feeding",
    )
    fake_ui.by_label(form._t("save_measurement")).on_click()
    assert saved == [form]

    form.reset_after_save()
    assert form._value.value is None
    assert form._note.value == ""
    assert form._datetime.value.tzinfo is not None


@pytest.mark.parametrize(
    ("parameter_id", "measurement_value", "message"),
    [
        (None, 5, "Select a parameter first."),
        ("invalid", 5, "Select a parameter first."),
        (1, None, "Measurement value must be a number."),
        (1, "invalid", "Measurement value must be a number."),
    ],
)
def test_measurement_form_rejects_missing_or_invalid_values(
    monkeypatch, parameter_id, measurement_value, message
):
    install_ui(monkeypatch, measurement_form_module)
    install_datetime_picker(monkeypatch, measurement_form_module)
    form = MeasurementForm("en", lambda _: None)
    form._parameter.value = parameter_id
    form._value.value = measurement_value

    with pytest.raises(ValidationError, match=message):
        form.values
