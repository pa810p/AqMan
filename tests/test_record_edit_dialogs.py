from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from aqman.models import WaterSource
from aqman.services import NotFoundError, ValidationError
from aqman.ui.components import record_edit_dialogs as dialogs_module
from aqman.ui.components.record_edit_dialogs import RecordEditDialogs
from component_ui import install_datetime_picker, install_ui


TIMESTAMP = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def build_dialogs(monkeypatch):
    fake_ui = install_ui(monkeypatch, dialogs_module)
    install_datetime_picker(monkeypatch, dialogs_module)
    record_service = Mock()
    parameter_service = Mock()
    fertilizer_service = Mock()
    saved = []
    errors = []
    dialogs = RecordEditDialogs(
        record_service,
        parameter_service,
        fertilizer_service,
        lambda: 23,
        "en",
        {"ro": "RO", "tap": "Tap"},
        lambda: saved.append(True),
        errors.append,
    )
    return fake_ui, dialogs, record_service, parameter_service, fertilizer_service, saved, errors


def test_note_dialog_updates_and_reports_service_error(monkeypatch):
    fake_ui, dialogs, records, _, _, saved, errors = build_dialogs(monkeypatch)
    note = SimpleNamespace(id=4, timestamp=TIMESTAMP, category=None, content="Old")
    records.get_note.return_value = note
    records.update_note.side_effect = ValidationError("invalid note")

    dialogs.open_note(4)
    assert fake_ui.dialogs[0].opened
    fake_ui.by_label(dialogs._t("optional_category")).value = "care"
    fake_ui.by_label(dialogs._t("note_content")).value = "Trimmed plants"
    fake_ui.by_label(dialogs._t("save")).on_click()

    records.update_note.assert_called_once_with(
        23, 4, TIMESTAMP, "care", "Trimmed plants"
    )
    assert len(errors) == 1
    assert isinstance(errors[0], ValidationError)
    assert saved == []
    assert not getattr(fake_ui.dialogs[0], "closed", False)

    records.update_note.side_effect = None
    fake_ui.by_label(dialogs._t("save")).on_click()
    assert saved == [True]
    assert fake_ui.dialogs[0].closed
    assert fake_ui.notifications[-1] == (dialogs._t("updated_note"), "positive")


def test_note_get_failure_is_reported_without_opening_dialog(monkeypatch):
    fake_ui, dialogs, records, _, _, saved, errors = build_dialogs(monkeypatch)
    failure = NotFoundError("note missing")
    records.get_note.side_effect = failure

    dialogs.open_note(404)

    assert errors == [failure]
    assert saved == []
    assert fake_ui.dialogs == []


def test_measurement_invalid_parameter_save_and_delete_paths(monkeypatch):
    fake_ui, dialogs, records, parameters, _, saved, errors = build_dialogs(monkeypatch)
    measurement = SimpleNamespace(
        id=9, timestamp=TIMESTAMP, parameter_id=2, value=6.5, note=None
    )
    records.get_measurement.return_value = measurement
    parameters.list_parameters.return_value = [
        SimpleNamespace(id=2, name="NO3", unit="mg/L")
    ]

    dialogs.open_measurement(9)
    assert fake_ui.by_label(dialogs._t("parameter")).options == {2: "NO3 (mg/L)"}
    fake_ui.by_label(dialogs._t("parameter")).value = None
    fake_ui.by_label(dialogs._t("save")).on_click()
    assert isinstance(errors[-1], ValidationError)
    assert not getattr(fake_ui.dialogs[0], "closed", False)

    open_delete_confirmation = fake_ui.by_label(dialogs._t("delete_measurement"))
    open_delete_confirmation.on_click()
    confirmation = fake_ui.dialogs[1]
    assert confirmation.opened
    records.delete_measurement.side_effect = NotFoundError("already gone")
    fake_ui.by_label(dialogs._t("delete_measurement")).on_click()
    assert isinstance(errors[-1], NotFoundError)
    assert confirmation.closed
    assert not getattr(fake_ui.dialogs[0], "closed", False)

    fake_ui.by_label(dialogs._t("parameter")).value = "2"
    fake_ui.by_label(dialogs._t("save")).on_click()
    records.update_measurement.assert_called_once_with(
        23, 9, TIMESTAMP, 2, 6.5, ""
    )
    assert saved == [True]
    assert fake_ui.dialogs[0].closed

    open_delete_confirmation.on_click()
    records.delete_measurement.side_effect = None
    fake_ui.by_label(dialogs._t("delete_measurement")).on_click()
    assert records.delete_measurement.call_count == 2
    assert fake_ui.dialogs[0].closed
    assert saved == [True, True]


def test_measurement_lookup_failure_reports_error(monkeypatch):
    fake_ui, dialogs, records, _, _, saved, errors = build_dialogs(monkeypatch)
    failure = ValidationError("bad id")
    records.get_measurement.side_effect = failure

    dialogs.open_measurement(9)

    assert errors == [failure]
    assert saved == []
    assert fake_ui.dialogs == []


def test_fertilizer_application_edit_and_invalid_fertilizer(monkeypatch):
    fake_ui, dialogs, records, _, fertilizers, saved, errors = build_dialogs(monkeypatch)
    application = SimpleNamespace(
        id=6, timestamp=TIMESTAMP, fertilizer_id=7, actual_dose_ml=3.5, notes=None
    )
    records.get_fertilizer_application.return_value = application
    fertilizers.list_fertilizers.return_value = [
        SimpleNamespace(id=7, name="Nitrate")
    ]

    dialogs.open_fertilizer_application(6)
    assert fake_ui.by_label(dialogs._t("fertilizer")).options == {7: "Nitrate"}
    fake_ui.by_label(dialogs._t("fertilizer")).value = "bad"
    fake_ui.by_label(dialogs._t("save")).on_click()
    assert isinstance(errors[-1], ValidationError)
    assert not getattr(fake_ui.dialogs[0], "closed", False)

    fake_ui.by_label(dialogs._t("fertilizer")).value = "7"
    fake_ui.by_label(dialogs._t("save")).on_click()
    records.update_fertilizer_application.assert_called_once_with(
        23, 6, TIMESTAMP, 7, 3.5, ""
    )
    assert saved == [True]
    assert fake_ui.notifications[-1] == (
        dialogs._t("updated_fertilizer_application"),
        "positive",
    )

    open_delete_confirmation = fake_ui.by_label(
        dialogs._t("delete_fertilizer_application")
    )
    open_delete_confirmation.on_click()
    confirmation = fake_ui.dialogs[1]
    records.delete_fertilizer_application.side_effect = ValidationError("in use")
    fake_ui.by_label(dialogs._t("delete_fertilizer_application")).on_click()
    assert isinstance(errors[-1], ValidationError)
    assert confirmation.closed

    open_delete_confirmation.on_click()
    records.delete_fertilizer_application.side_effect = None
    fake_ui.by_label(dialogs._t("delete_fertilizer_application")).on_click()
    assert records.delete_fertilizer_application.call_count == 2
    assert fake_ui.dialogs[0].closed
    assert saved == [True, True]


def test_fertilizer_application_lookup_failure(monkeypatch):
    fake_ui, dialogs, records, _, _, saved, errors = build_dialogs(monkeypatch)
    failure = NotFoundError("application missing")
    records.get_fertilizer_application.side_effect = failure

    dialogs.open_fertilizer_application(404)

    assert errors == [failure]
    assert saved == []
    assert fake_ui.dialogs == []


def test_water_change_invalid_source_and_successful_update(monkeypatch):
    fake_ui, dialogs, records, _, _, saved, errors = build_dialogs(monkeypatch)
    water_change = SimpleNamespace(
        id=5,
        timestamp=TIMESTAMP,
        source=WaterSource.RO,
        volume_liters=20,
        description=None,
    )
    records.get_water_change.return_value = water_change

    dialogs.open_water_change(5)
    fake_ui.by_label(dialogs._t("water_source")).value = "other"
    fake_ui.by_label(dialogs._t("save")).on_click()
    assert isinstance(errors[-1], ValidationError)
    assert not getattr(fake_ui.dialogs[0], "closed", False)

    fake_ui.by_label(dialogs._t("water_source")).value = WaterSource.RO.value
    fake_ui.by_label(dialogs._t("save")).on_click()
    records.update_water_change.assert_called_once_with(
        23, 5, TIMESTAMP, WaterSource.RO, 20, ""
    )
    assert saved == [True]
    assert fake_ui.dialogs[0].closed
    assert fake_ui.notifications[-1] == (
        dialogs._t("updated_water_change"),
        "positive",
    )


def test_water_change_lookup_failure(monkeypatch):
    fake_ui, dialogs, records, _, _, saved, errors = build_dialogs(monkeypatch)
    failure = NotFoundError("water change missing")
    records.get_water_change.side_effect = failure

    dialogs.open_water_change(404)

    assert errors == [failure]
    assert saved == []
    assert fake_ui.dialogs == []
