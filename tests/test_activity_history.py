from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from aqman.models import Measurement, Note, Parameter, WaterChange, WaterSource
from aqman.services import NotFoundError, ValidationError
from aqman.models import Fertilizer, FertilizerApplication
from aqman.services import DailyAquariumHistory
from aqman.ui.components import activity_history as activity_history_module
from aqman.ui.components.activity_history import ActivityHistory


class FakeElement:
    def __init__(self, **attributes):
        self.__dict__.update(attributes)
        self.classes_calls = []
        self.slots = {}
        self.handlers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def classes(self, value):
        self.classes_calls.append(value)
        return self

    def clear(self):
        self.cleared = True

    def add_slot(self, name, content):
        self.slots[name] = content

    def on(self, name, callback):
        self.handlers[name] = callback


class FakeHistoryUI:
    def __init__(self):
        self.labels = []
        self.tables = []

    def card(self):
        return FakeElement()

    def column(self):
        return FakeElement()

    def label(self, text=""):
        label = FakeElement(text=text)
        self.labels.append(label)
        return label

    def table(self, **kwargs):
        table = FakeElement(**kwargs)
        self.tables.append(table)
        return table


def _make_history(
    *,
    aquarium_id_provider=lambda: 3,
    daily_history=None,
):
    service = Mock()
    service.daily_history.return_value = daily_history or []
    errors = []
    dialogs = Mock()
    history = ActivityHistory(
        service,
        aquarium_id_provider,
        "en",
        {WaterSource.RO: "RO", WaterSource.TAP: "Tap", WaterSource.MIXED: "Mixed"},
        lambda: dialogs,
        errors.append,
    )
    return history, service, errors, dialogs


def test_history_table_has_a_separate_column_for_each_fertilizer() -> None:
    nitrate = Fertilizer(id=4, name="Nitrate", dose_ml_per_100l=5)
    macro = Fertilizer(id=11, name="Macro", dose_ml_per_100l=10)
    first_application = FertilizerApplication(
        id=1,
        timestamp=datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
        aquarium_id=1,
        fertilizer_id=nitrate.id,
        actual_dose_ml=2.5,
        fertilizer=nitrate,
    )
    second_nitrate_application = FertilizerApplication(
        id=3,
        timestamp=datetime(2026, 10, 30, 18, 0, tzinfo=timezone.utc),
        aquarium_id=1,
        fertilizer_id=nitrate.id,
        actual_dose_ml=1,
        fertilizer=nitrate,
    )
    second_application = FertilizerApplication(
        id=2,
        timestamp=datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
        aquarium_id=1,
        fertilizer_id=macro.id,
        actual_dose_ml=4,
        fertilizer=macro,
    )
    first_day = DailyAquariumHistory(
        day=date(2026, 10, 30),
        measurements={},
        water_changes=(),
        notes=(),
        fertilizer_applications=(first_application, second_nitrate_application),
    )
    second_day = DailyAquariumHistory(
        day=date(2026, 10, 31),
        measurements={},
        water_changes=(),
        notes=(),
        fertilizer_applications=(second_application,),
    )
    history = ActivityHistory.__new__(ActivityHistory)
    history._language = "en"

    columns, parameter_ids, fertilizer_ids = history._history_columns(
        [first_day, second_day]
    )
    row = history._history_row(first_day, parameter_ids, fertilizer_ids)

    assert fertilizer_ids == [11, 4]
    assert [
        (column["name"], column["label"])
        for column in columns
        if column["name"].startswith("fertilizer_")
    ] == [
        ("fertilizer_11", "Macro"),
        ("fertilizer_4", "Nitrate"),
    ]
    assert all(
        "classes" not in column and "headerClasses" not in column
        for column in columns
        if column["name"].startswith("fertilizer_")
    )
    water_change_column = next(
        column for column in columns if column["name"] == "water_changes"
    )
    assert "classes" not in water_change_column
    assert "headerClasses" not in water_change_column
    assert row["fertilizer_4"] == [
        {"id": 1, "label": "2.5 ml"},
        {"id": 3, "label": "1 ml"},
    ]
    assert row["fertilizer_11"] == []
    assert "fertilizer_applications" not in row


def test_refresh_renders_daily_rows_slots_and_edit_handlers(monkeypatch) -> None:
    fake_ui = FakeHistoryUI()
    monkeypatch.setattr(activity_history_module, "ui", fake_ui)
    parameter = Parameter(id=5, name="pH", unit="pH")
    fertilizer = Fertilizer(id=8, name="Macro", dose_ml_per_100l=5)
    measurement = Measurement(
        id=11,
        aquarium_id=3,
        timestamp=datetime(2026, 10, 30, 12, tzinfo=timezone.utc),
        parameter_id=5,
        value=7.25,
        note="stable water after the change",
        parameter=parameter,
    )
    note = Note(
        id=12,
        aquarium_id=3,
        timestamp=datetime(2026, 10, 30, 13, tzinfo=timezone.utc),
        content="Observed new growth",
    )
    water_change = WaterChange(
        id=13,
        aquarium_id=3,
        timestamp=datetime(2026, 10, 30, 14, tzinfo=timezone.utc),
        source=WaterSource.RO,
        volume_liters=20,
        description="weekly service",
    )
    application = FertilizerApplication(
        id=14,
        timestamp=datetime(2026, 10, 30, 15, tzinfo=timezone.utc),
        aquarium_id=3,
        fertilizer_id=8,
        actual_dose_ml=2.5,
        notes="added after testing",
        fertilizer=fertilizer,
    )
    day = DailyAquariumHistory(
        day=date(2026, 10, 30),
        measurements={5: (measurement,)},
        water_changes=(water_change,),
        notes=(note,),
        fertilizer_applications=(application,),
    )
    history, service, _, _ = _make_history(daily_history=[day])
    history._aquarium_id_provider = lambda: 3

    history.refresh()

    service.daily_history.assert_called_once_with(3)
    table = fake_ui.tables[0]
    assert table.row_key == "id"
    assert table.rows[0]["parameter_5"] == [{"id": 11, "value": "7.25"}]
    assert table.rows[0]["water_changes"][0]["label"] == (
        "RO: 20 L (weekly service)"
    )
    assert {link["id"] for link in table.rows[0]["notes"]} == {
        "note-12",
        "measurement-11",
        "fertilizer-application-14",
    }
    assert set(table.slots) == {
        "body-cell-parameter_5",
        "body-cell-fertilizer_8",
        "body-cell-water_changes",
        "body-cell-notes",
    }
    assert "measurement-edit-click" in table.handlers
    assert "fertilizer-application-edit-click" in table.handlers
    assert "water-change-edit-click" in table.handlers
    assert "note-edit-click" in table.handlers


@pytest.mark.parametrize(
    ("provider", "expected_service_calls"),
    [
        (
            lambda: (_ for _ in ()).throw(ValidationError("choose an aquarium")),
            0,
        ),
        (lambda: 3, 1),
    ],
)
def test_refresh_shows_empty_state_for_missing_aquarium_or_history(
    monkeypatch,
    provider,
    expected_service_calls,
) -> None:
    fake_ui = FakeHistoryUI()
    monkeypatch.setattr(activity_history_module, "ui", fake_ui)
    history, service, _, _ = _make_history(aquarium_id_provider=provider)

    history.refresh()

    assert fake_ui.tables == []
    assert fake_ui.labels[-1].text == (
        "No activity has been recorded for this aquarium yet."
    )
    assert service.daily_history.call_count == expected_service_calls


def test_history_formats_water_change_without_description_and_note_previews() -> None:
    history = ActivityHistory.__new__(ActivityHistory)
    history._language = "en"
    history._water_source_labels = {WaterSource.TAP: "Tap"}
    water_change = WaterChange(
        id=1,
        aquarium_id=3,
        timestamp=datetime(2026, 10, 30, tzinfo=timezone.utc),
        source=WaterSource.TAP,
        volume_liters=12,
        description=None,
    )

    assert history._format_water_change(water_change) == "Tap: 12 L"
    assert history._note_preview("  short   note ") == "short note"
    assert history._note_preview("one two three four five six seven eight") == (
        "one two three four five six…"
    )


def test_edit_handlers_route_valid_ids_and_report_malformed_events() -> None:
    history = ActivityHistory.__new__(ActivityHistory)
    history._edit_dialogs_provider = Mock(return_value=Mock())
    history._on_error = Mock()

    for event_value, method, expected in [
        ("note-21", "open_note", 21),
        ("measurement-22", "open_measurement", 22),
        ("fertilizer-application-23", "open_fertilizer_application", 23),
    ]:
        history._handle_note_edit(SimpleNamespace(args=event_value))
        getattr(history._edit_dialogs_provider.return_value, method).assert_called_with(
            expected
        )

    history._handle_note_edit(SimpleNamespace(args="unknown-24"))
    history._handle_note_edit(SimpleNamespace(args="note-not-an-id"))
    history._handle_note_edit(SimpleNamespace(args="missing"))
    history._handle_measurement_edit(SimpleNamespace(args="bad"))
    history._handle_measurement_edit(SimpleNamespace(args=None))
    history._handle_water_change_edit(SimpleNamespace(args="bad"))
    history._handle_fertilizer_application_edit(SimpleNamespace(args="bad"))

    assert history._on_error.call_count == 7
    assert all(
        isinstance(call.args[0], NotFoundError)
        for call in history._on_error.call_args_list
    )


def test_record_edit_handlers_dispatch_and_reject_invalid_ids() -> None:
    history = ActivityHistory.__new__(ActivityHistory)
    dialogs = Mock()
    history._edit_dialogs_provider = lambda: dialogs
    history._on_error = Mock()

    history._handle_measurement_edit(SimpleNamespace(args="17"))
    history._handle_water_change_edit(SimpleNamespace(args=18))
    history._handle_fertilizer_application_edit(SimpleNamespace(args="19"))
    history._handle_measurement_edit(SimpleNamespace(args="invalid"))
    history._handle_water_change_edit(SimpleNamespace(args=None))
    history._handle_fertilizer_application_edit(SimpleNamespace(args="invalid"))

    dialogs.open_measurement.assert_called_once_with(17)
    dialogs.open_water_change.assert_called_once_with(18)
    dialogs.open_fertilizer_application.assert_called_once_with(19)
    assert history._on_error.call_count == 3
