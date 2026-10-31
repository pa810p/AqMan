from datetime import datetime, timezone
import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from aqman.models import WaterSource
from aqman.services import NotFoundError, ValidationError
from aqman.ui import (
    _format_datetime,
)
ui_module = importlib.import_module("aqman.ui")
from aqman.ui.components.date_time_picker import (
    _local_datetime_input_value,
    _local_datetime_parts,
    _parse_local_datetime_value,
)


def test_local_datetime_parts_use_24_hour_time() -> None:
    value = datetime(2026, 10, 30, 17, 35, tzinfo=timezone.utc)

    date_value, time_value = _local_datetime_parts(value)

    assert date_value == value.astimezone().strftime("%Y-%m-%d")
    assert time_value == value.astimezone().strftime("%H:%M")
    assert len(time_value) == 5


def test_combined_datetime_input_uses_iso_value() -> None:
    value = datetime(2026, 10, 31, 10, 45, tzinfo=timezone.utc)

    assert _local_datetime_input_value(value) == value.astimezone().strftime(
        "%Y-%m-%d %H:%M"
    )


def test_date_only_datetime_input_uses_iso_date() -> None:
    value = datetime(2026, 10, 31, 10, 45, tzinfo=timezone.utc)

    assert _local_datetime_input_value(value, show_time=False) == (
        value.astimezone().strftime("%Y-%m-%d")
    )


def test_parse_combined_datetime_input_converts_local_time_to_utc() -> None:
    expected = datetime(2026, 10, 30, 17, 35).astimezone(timezone.utc)

    assert _parse_local_datetime_value("2026-10-30 17:35") == expected


def test_parse_date_only_datetime_input_uses_local_midnight_in_utc() -> None:
    expected = datetime(2026, 10, 30).astimezone(timezone.utc)

    assert _parse_local_datetime_value(
        "2026-10-30",
        show_time=False,
    ) == expected


@pytest.mark.parametrize(
    "value",
    [None, "", "2026-10-30", "30-10-2026 17:35", "2026-10-30 25:00"],
)
def test_parse_combined_datetime_input_rejects_missing_or_invalid_values(
    value: str | None,
) -> None:
    with pytest.raises(ValidationError):
        _parse_local_datetime_value(value)


def test_format_datetime_uses_iso_date_order() -> None:
    value = datetime(2026, 10, 30, 17, 35, tzinfo=timezone.utc)

    assert _format_datetime(value, "en") == value.astimezone().strftime("%Y-%m-%d %H:%M")


class FakeElement:
    def __init__(self, text: str | None = None, on_click=None) -> None:
        self.text = text
        self.on_click = on_click
        self.visible = True
        self.value = None
        self.updated = False
        self.cleared = False

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def classes(self, *_args: str):
        return self

    def props(self, *_args: str):
        return self

    def tooltip(self, *_args: str):
        return self

    def on(self, _event: str, callback):
        self.on_click = callback
        return self

    def clear(self) -> None:
        self.cleared = True

    def update(self) -> None:
        self.updated = True

    def set_visibility(self, visible: bool) -> None:
        self.visible = visible


class FakeTabs(FakeElement):
    pass


class FakeUI:
    def __init__(self) -> None:
        self.labels: list[str] = []
        self.buttons: list[FakeElement] = []
        self.columns: list[FakeElement] = []
        self.notifications: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.colors_value: dict[str, str] | None = None
        self.head_html: list[str] = []
        self.navigation: list[str] = []
        self.context = SimpleNamespace(client=SimpleNamespace(page=SimpleNamespace()))
        self.navigate = SimpleNamespace(to=self.navigation.append)

    def colors(self, **colors: str) -> None:
        self.colors_value = colors

    def dark_mode(self):
        return SimpleNamespace(enable=lambda: None)

    def add_head_html(self, html: str) -> None:
        self.head_html.append(html)

    def header(self):
        return FakeElement()

    def row(self):
        return FakeElement()

    def column(self):
        element = FakeElement()
        self.columns.append(element)
        return element

    def tabs(self):
        return FakeTabs()

    def tab(self, text: str):
        return FakeElement(text=text)

    def tab_panels(self, *_args: object, **_kwargs: object):
        return FakeElement()

    def tab_panel(self, *_args: object, **_kwargs: object):
        return FakeElement()

    def grid(self, **_kwargs: object):
        return FakeElement()

    def element(self, *_args: object, **_kwargs: object):
        return FakeElement()

    def card(self):
        return FakeElement()

    def label(self, text: str):
        self.labels.append(text)
        return FakeElement(text=text)

    def button(self, *args: object, **kwargs: object):
        text = str(args[0]) if args else None
        callback = kwargs.get("on_click")
        element = FakeElement(text, callback if callable(callback) else None)
        self.buttons.append(element)
        return element

    def image(self, *_args: object, **_kwargs: object):
        return FakeElement()

    def icon(self, *_args: object, **_kwargs: object):
        return FakeElement()

    def separator(self):
        return FakeElement()

    def notify(self, *args: object, **kwargs: object) -> None:
        self.notifications.append((args, kwargs))


class FakeComponent:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.refresh_calls = 0
        self.reset_calls = 0
        self.opened: list[object] = []
        self.values = None

    def refresh(self) -> None:
        self.refresh_calls += 1

    def set_parameters(self, _parameters: object) -> None:
        return None

    def set_fertilizers(self, _fertilizers: object) -> None:
        return None

    def reset_after_save(self) -> None:
        self.reset_calls += 1

    def open(self, *args: object) -> None:
        self.opened.append(args[0] if args else None)


def _component_factory(instances: dict[str, list[FakeComponent]], name: str):
    def factory(*args: object, **kwargs: object) -> FakeComponent:
        component = FakeComponent(**kwargs)
        component.args = args
        instances[name].append(component)
        return component

    return factory


@pytest.fixture
def ui_assembly(monkeypatch: pytest.MonkeyPatch):
    fake_ui = FakeUI()
    monkeypatch.setattr(ui_module, "ui", fake_ui)
    names = (
        "ActivityHistory",
        "AquariumCharts",
        "AquariumDialog",
        "FertilizerCatalog",
        "FertilizerApplicationForm",
        "MeasurementForm",
        "NoteForm",
        "ParameterCatalog",
        "RecordEditDialogs",
        "WaterChangeForm",
    )
    instances = {name: [] for name in names}
    for name in names:
        monkeypatch.setattr(
            ui_module,
            name,
            _component_factory(instances, name),
        )

    aquarium = SimpleNamespace(
        id=7,
        name="Planted tank",
        volume_liters=120,
        description="Living room aquarium",
        active=False,
        thumbnail_data=None,
    )
    dashboard_entry = SimpleNamespace(
        aquarium=aquarium,
        last_measurement_at=None,
    )
    aquarium_service = Mock()
    aquarium_service.dashboard.return_value = [dashboard_entry]
    aquarium_service.list_aquariums.return_value = [aquarium]
    parameter_service = Mock()
    fertilizer_service = Mock()
    record_service = Mock()
    ui_module.build_ui(
        aquarium_service,
        parameter_service,
        fertilizer_service,
        record_service,
        language="unsupported",
        show_time_in_datetime_picker=False,
    )
    return (
        fake_ui,
        instances,
        aquarium,
        aquarium_service,
        parameter_service,
        fertilizer_service,
        record_service,
    )


def _click_button(fake_ui: FakeUI, label: str, occurrence: int = 0) -> None:
    matching = [button for button in fake_ui.buttons if button.text == label]
    button = matching[occurrence]
    assert button.on_click is not None
    button.on_click()


def test_build_ui_assembles_components_and_initial_dashboard(ui_assembly) -> None:
    (
        fake_ui,
        instances,
        _aquarium,
        _aquarium_service,
        _parameter_service,
        _fertilizer_service,
        _record_service,
    ) = ui_assembly

    assert fake_ui.context.client.page.language == "en-US"
    assert fake_ui.colors_value is not None
    assert fake_ui.head_html == [ui_module.THEME_CSS]
    assert "Planted tank" in fake_ui.labels
    assert any("No measurements" in label for label in fake_ui.labels)
    assert instances["MeasurementForm"][0].kwargs["show_time"] is False
    assert instances["FertilizerApplicationForm"][0].kwargs["show_time"] is False
    assert instances["AquariumCharts"][0].kwargs["show_time"] is False
    assert instances["ActivityHistory"][0].refresh_calls == 1
    assert instances["AquariumCharts"][0].refresh_calls == 1


def test_build_ui_callbacks_navigate_select_and_save_records(ui_assembly) -> None:
    (
        fake_ui,
        instances,
        aquarium,
        aquarium_service,
        _parameter_service,
        _fertilizer_service,
        record_service,
    ) = ui_assembly

    _click_button(fake_ui, "🇵🇱")
    assert fake_ui.navigation == ["/?lang=pl"]

    _click_button(fake_ui, "Open aquarium")
    assert instances["ActivityHistory"][0].refresh_calls == 2
    assert instances["AquariumCharts"][0].refresh_calls == 2

    _click_button(fake_ui, "Edit aquarium")
    assert instances["AquariumDialog"][0].opened == [aquarium]

    _click_button(fake_ui, "Restore")
    aquarium_service.set_active.assert_called_once_with(aquarium.id, True)

    timestamp = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    measurement = instances["MeasurementForm"][0]
    measurement.values = SimpleNamespace(
        timestamp=timestamp,
        parameter_id=3,
        value=8.2,
        note="morning",
    )
    measurement.kwargs["on_save"](measurement)
    record_service.record_measurement.assert_called_once_with(
        aquarium.id,
        timestamp,
        3,
        8.2,
        "morning",
    )
    assert measurement.reset_calls == 1

    note = instances["NoteForm"][0]
    note.values = SimpleNamespace(
        timestamp=timestamp,
        category="maintenance",
        content="Cleaned filter",
    )
    note.kwargs["on_save"](note)
    record_service.add_note.assert_called_once_with(
        aquarium.id,
        timestamp,
        "maintenance",
        "Cleaned filter",
    )

    water_change = instances["WaterChangeForm"][0]
    water_change.values = SimpleNamespace(
        timestamp=timestamp,
        source=WaterSource.RO,
        volume_liters=20,
        description="weekly change",
    )
    water_change.kwargs["on_save"](water_change)
    record_service.add_water_change.assert_called_once_with(
        aquarium.id,
        timestamp,
        WaterSource.RO,
        20,
        "weekly change",
    )

    fertilizer_application = instances["FertilizerApplicationForm"][0]
    fertilizer_application.values = SimpleNamespace(
        timestamp=timestamp,
        fertilizer_id=5,
        actual_dose_ml=2.5,
        notes="",
    )
    fertilizer_application.kwargs["on_save"](fertilizer_application)
    record_service.add_fertilizer_application.assert_called_once_with(
        aquarium.id,
        timestamp,
        5,
        2.5,
        "",
    )

    assert len(fake_ui.notifications) == 4
    assert all(
        notification[1]["type"] == "positive"
        for notification in fake_ui.notifications
    )


def test_build_ui_reports_missing_selection_and_missing_aquarium(ui_assembly) -> None:
    (
        fake_ui,
        _instances,
        _aquarium,
        aquarium_service,
        _parameter_service,
        _fertilizer_service,
        record_service,
    ) = ui_assembly

    _click_button(fake_ui, "Edit aquarium")
    assert fake_ui.notifications[-1] == (
        ("Select an aquarium first.",),
        {"type": "negative"},
    )

    _click_button(fake_ui, "Open aquarium")
    aquarium_service.list_aquariums.return_value = []
    _click_button(fake_ui, "Edit aquarium")
    assert fake_ui.notifications[-1] == (
        ("Aquarium not found.",),
        {"type": "negative"},
    )

    record_service.record_measurement.side_effect = ValidationError("Invalid value.")
    measurement = _instances["MeasurementForm"][0]
    measurement.values = SimpleNamespace(
        timestamp=datetime(2026, 10, 31, tzinfo=timezone.utc),
        parameter_id=3,
        value=-1,
        note=None,
    )
    measurement.kwargs["on_save"](measurement)
    assert fake_ui.notifications[-1] == (
        ("Invalid value.",),
        {"type": "negative"},
    )
    assert measurement.reset_calls == 0

    aquarium_service.set_active.side_effect = NotFoundError("Aquarium not found.")
    _click_button(fake_ui, "Restore")
    assert fake_ui.notifications[-1] == (
        ("Aquarium not found.",),
        {"type": "negative"},
    )
