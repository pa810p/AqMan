import pytest

from aqman.models import WaterSource
from aqman.services import ValidationError
from aqman.ui.components import water_change_form as water_change_form_module
from aqman.ui.components.water_change_form import WaterChangeForm
from component_ui import install_datetime_picker, install_ui


def test_water_change_form_values_save_callback_and_reset(monkeypatch):
    fake_ui = install_ui(monkeypatch, water_change_form_module)
    install_datetime_picker(monkeypatch, water_change_form_module)
    saved = []
    form = WaterChangeForm("en", {"ro": "RO", "tap": "Tap"}, saved.append)
    assert form._source.value == WaterSource.RO.value
    form._volume.value = "12.5"
    form._description.value = "Weekly change"

    values = form.values
    assert values.source is WaterSource.RO
    assert values.volume_liters == 12.5
    assert values.description == "Weekly change"
    fake_ui.by_label(form._t("save_water_change")).on_click()
    assert saved == [form]

    form.reset_after_save()
    assert form._volume.value is None
    assert form._description.value == ""
    assert form._datetime.value.tzinfo is not None


@pytest.mark.parametrize(
    ("source", "volume", "message"),
    [
        ("invalid", 5, "Select a valid water source."),
        (None, 5, "Select a valid water source."),
        (WaterSource.RO.value, None, "Water-change volume must be a number."),
        (WaterSource.RO.value, "bad", "Water-change volume must be a number."),
    ],
)
def test_water_change_form_rejects_invalid_values(
    monkeypatch, source, volume, message
):
    install_ui(monkeypatch, water_change_form_module)
    install_datetime_picker(monkeypatch, water_change_form_module)
    form = WaterChangeForm("en", {}, lambda _: None)
    form._source.value = source
    form._volume.value = volume

    with pytest.raises(ValidationError, match=message):
        form.values
