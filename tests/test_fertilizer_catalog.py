from types import SimpleNamespace

import pytest

from aqman.services import NotFoundError, ValidationError
from aqman.ui.components import fertilizer_catalog as catalog_module
from aqman.ui.components.fertilizer_catalog import FertilizerCatalog
from component_ui import install_ui


def make_parameter(parameter_id, name, unit="mg/L"):
    return SimpleNamespace(id=parameter_id, name=name, unit=unit)


def make_fertilizer(fertilizer_id=4, name="Nitrate", effects=None):
    parameter = make_parameter(1, "NO3")
    return SimpleNamespace(
        id=fertilizer_id,
        name=name,
        dose_ml_per_100l=5,
        effects=effects
        if effects is not None
        else [
            SimpleNamespace(
                parameter_id=1,
                parameter=parameter,
                ppm_per_dose=2.5,
            )
        ],
    )


class FertilizerService:
    def __init__(self):
        self.fertilizers = []
        self.parameters = [make_parameter(1, "NO3"), make_parameter(2, "PO4")]
        self.get_error = None
        self.save_error = None
        self.delete_error = None
        self.created = []
        self.updated = []
        self.deleted = []

    def list_fertilizers(self):
        return self.fertilizers

    def list_effect_parameters(self):
        return self.parameters

    def get_fertilizer(self, fertilizer_id):
        if self.get_error:
            raise self.get_error
        return next(item for item in self.fertilizers if item.id == fertilizer_id)

    def create_fertilizer(self, *args):
        if self.save_error:
            raise self.save_error
        self.created.append(args)

    def update_fertilizer(self, *args):
        if self.save_error:
            raise self.save_error
        self.updated.append(args)

    def delete_fertilizer(self, fertilizer_id):
        if self.delete_error:
            raise self.delete_error
        self.deleted.append(fertilizer_id)


def build_catalog(monkeypatch, service):
    fake_ui = install_ui(monkeypatch, catalog_module)
    changed = []
    saved = []
    errors = []
    catalog = FertilizerCatalog(
        service,
        "en",
        changed.append,
        lambda: saved.append(True),
        errors.append,
    )
    return fake_ui, catalog, changed, saved, errors


def test_refresh_renders_empty_and_populated_catalog(monkeypatch):
    service = FertilizerService()
    fake_ui, catalog, changed, _, _ = build_catalog(monkeypatch, service)

    catalog.refresh()
    assert changed == [[]]
    assert catalog._container.cleared
    assert fake_ui.by_label(catalog._t("empty_fertilizers"))

    service.fertilizers = [make_fertilizer()]
    catalog.refresh()
    assert changed[-1] == service.fertilizers
    assert fake_ui.by_label("Nitrate")
    assert fake_ui.by_label(catalog._t("fertilizer_effect_line", parameter="NO3 (mg/L)", ppm=2.5))


def test_create_dialog_adds_removes_and_saves_effect_rows(monkeypatch):
    service = FertilizerService()
    fake_ui, catalog, _, saved, errors = build_catalog(monkeypatch, service)

    catalog.open_dialog()
    parameter_inputs = [
        control
        for control in fake_ui.controls
        if control.label == catalog._t("fertilizer_effect_parameter")
    ]
    assert len(parameter_inputs) == 1
    only_row_remove = next(
        control
        for control in fake_ui.buttons()
        if control.kwargs.get("icon") == "close"
    )
    assert not only_row_remove.enabled
    only_row_remove.on_click()
    first_parameter = parameter_inputs[0]
    first_parameter.value = 1
    first_parameter.on_change(None)

    fake_ui.by_label(catalog._t("add_fertilizer_effect")).on_click()
    parameter_inputs = [
        control
        for control in fake_ui.controls
        if control.label == catalog._t("fertilizer_effect_parameter")
    ]
    assert len(parameter_inputs) == 2
    assert 1 not in parameter_inputs[1].options
    parameter_inputs[1].value = 2
    parameter_inputs[1].on_change(None)
    parameter_inputs[1].value = 1
    parameter_inputs[1].on_change(None)
    assert parameter_inputs[0].value is None

    remove_buttons = [
        control
        for control in fake_ui.buttons()
        if control.kwargs.get("icon") == "close"
    ]
    assert all(button.enabled for button in remove_buttons)
    remove_buttons[0].on_click()
    assert sum(button.enabled for button in remove_buttons) == 1

    remaining_parameter = [
        control
        for control in fake_ui.controls
        if control.label == catalog._t("fertilizer_effect_parameter")
    ][-1]
    remaining_parameter.value = 2
    ppm_input = [
        control
        for control in fake_ui.controls
        if control.label == catalog._t("fertilizer_effect_ppm")
    ][-1]
    ppm_input.value = "3.25"
    fake_ui.by_label(catalog._t("fertilizer_name")).value = "Phosphate"
    fake_ui.by_label(catalog._t("fertilizer_dose")).value = "8"
    fake_ui.by_label(catalog._t("save")).on_click()

    assert service.created == [("Phosphate", 8.0, [(2, 3.25)])]
    assert saved == [True]
    assert errors == []
    assert fake_ui.dialogs[0].closed


@pytest.mark.parametrize(
    ("dose", "parameter_id", "ppm", "message"),
    [
        (None, 1, 2, "Base dose must be a number."),
        (5, None, 2, "Select a water parameter for every fertilizer effect."),
        (5, "invalid", 2, "Select a water parameter for every fertilizer effect."),
        (5, 1, None, "Fertilizer effect must be a number."),
        ("bad", 1, 2, "Enter valid fertilizer values."),
    ],
)
def test_create_dialog_rejects_invalid_values(
    monkeypatch, dose, parameter_id, ppm, message
):
    service = FertilizerService()
    fake_ui, catalog, _, saved, errors = build_catalog(monkeypatch, service)
    catalog.open_dialog()
    fake_ui.by_label(catalog._t("fertilizer_name")).value = "Fertilizer"
    fake_ui.by_label(catalog._t("fertilizer_dose")).value = dose
    fake_ui.by_label(catalog._t("fertilizer_effect_parameter")).value = parameter_id
    fake_ui.by_label(catalog._t("fertilizer_effect_ppm")).value = ppm

    fake_ui.by_label(catalog._t("save")).on_click()

    assert len(errors) == 1
    assert isinstance(errors[0], ValidationError)
    assert message in str(errors[0])
    assert saved == []
    assert not getattr(fake_ui.dialogs[0], "closed", False)


def test_create_dialog_shows_empty_parameter_state(monkeypatch):
    service = FertilizerService()
    service.parameters = []
    fake_ui, catalog, _, saved, errors = build_catalog(monkeypatch, service)

    catalog.open_dialog()

    assert fake_ui.by_label(catalog._t("no_fertilizer_parameters"))
    fake_ui.by_label(catalog._t("fertilizer_name")).value = "Empty"
    fake_ui.by_label(catalog._t("fertilizer_dose")).value = 5
    fake_ui.by_label(catalog._t("save")).on_click()
    assert isinstance(errors[0], ValidationError)
    assert saved == []


def test_create_dialog_maps_service_error_to_callback(monkeypatch):
    service = FertilizerService()
    failure = ValidationError("already exists")
    service.save_error = failure
    fake_ui, catalog, _, saved, errors = build_catalog(monkeypatch, service)
    catalog.open_dialog()
    fake_ui.by_label(catalog._t("fertilizer_name")).value = "Nitrate"
    fake_ui.by_label(catalog._t("fertilizer_dose")).value = 5
    fake_ui.by_label(catalog._t("fertilizer_effect_parameter")).value = 1
    fake_ui.by_label(catalog._t("fertilizer_effect_ppm")).value = 2

    fake_ui.by_label(catalog._t("save")).on_click()

    assert errors == [failure]
    assert saved == []
    assert not getattr(fake_ui.dialogs[0], "closed", False)


def test_edit_dialog_updates_existing_fertilizer(monkeypatch):
    fertilizer = make_fertilizer()
    service = FertilizerService()
    service.fertilizers = [fertilizer]
    fake_ui, catalog, _, saved, errors = build_catalog(monkeypatch, service)

    catalog.open_dialog(fertilizer.id)
    assert fake_ui.by_label(catalog._t("fertilizer_name")).value == "Nitrate"
    fake_ui.by_label(catalog._t("fertilizer_name")).value = "Nitrate Plus"
    fake_ui.by_label(catalog._t("fertilizer_dose")).value = "6.5"
    fake_ui.by_label(catalog._t("save")).on_click()

    assert service.updated == [(4, "Nitrate Plus", 6.5, [(1, 2.5)])]
    assert saved == [True]
    assert errors == []
    assert fake_ui.dialogs[0].closed


def test_edit_missing_fertilizer_returns_error_without_opening_dialog(monkeypatch):
    service = FertilizerService()
    failure = NotFoundError("missing fertilizer")
    service.get_error = failure
    fake_ui, catalog, _, saved, errors = build_catalog(monkeypatch, service)

    catalog.open_dialog(404)

    assert errors == [failure]
    assert saved == []
    assert fake_ui.dialogs == []


def test_confirm_delete_success_and_error_refreshes_catalog(monkeypatch):
    service = FertilizerService()
    fake_ui, catalog, changed, saved, errors = build_catalog(monkeypatch, service)
    failure = ValidationError("fertilizer is used")
    service.delete_error = failure

    catalog.confirm_delete(4, "Nitrate")
    fake_ui.by_label(catalog._t("delete_fertilizer")).on_click()
    assert errors == [failure]
    assert fake_ui.dialogs[0].closed
    assert changed == [[]]

    service.delete_error = None
    catalog.confirm_delete(4, "Nitrate")
    fake_ui.by_label(catalog._t("delete_fertilizer")).on_click()
    assert service.deleted == [4]
    assert saved == [True]
    assert fake_ui.dialogs[1].closed
    assert fake_ui.notifications[-1] == (catalog._t("deleted_fertilizer"), "positive")
