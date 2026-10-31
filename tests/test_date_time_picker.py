from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from aqman.services import ValidationError
from aqman.ui.components import date_time_picker as picker_module
from aqman.ui.components.date_time_picker import (
    DateTimePicker,
    _parse_local_datetime_value,
)


class FakeElement:
    def __init__(self, value=None, on_scroll=None):
        self.value = value
        self.on_scroll = on_scroll
        self.events = {}
        self.classes_calls = []
        self.styles = []
        self.updated = 0
        self.scroll_positions = []
        self.opened = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def add_slot(self, _name):
        return self

    def props(self, _):
        return self

    def classes(self, *args, **kwargs):
        self.classes_calls.append((args, kwargs))
        return self

    def style(self, value):
        self.styles.append(value)
        return self

    def on(self, name, callback):
        self.events[name] = callback
        return self

    def on_value_change(self, callback):
        self.events["value_change"] = callback

    def update(self):
        self.updated += 1

    def scroll_to(self, *, pixels):
        self.scroll_positions.append(pixels)

    def open(self):
        self.opened = True


class FakePickerUI:
    def __init__(self):
        self.inputs = []
        self.dates = []
        self.labels = []
        self.wheels = []
        self.timers = []

    def input(self, _label, value):
        element = FakeElement(value=value)
        self.inputs.append(element)
        return element

    def menu(self):
        return FakeElement()

    def row(self):
        return FakeElement()

    def column(self):
        return FakeElement()

    def label(self, text):
        element = FakeElement(value=text)
        element.text = text
        self.labels.append(element)
        return element

    def date(self, value, **_kwargs):
        element = FakeElement(value=value)
        self.dates.append(element)
        return element

    def icon(self, _name):
        return FakeElement()

    def scroll_area(self, *, on_scroll):
        element = FakeElement(on_scroll=on_scroll)
        self.wheels.append(element)
        return element

    def element(self, _name):
        return FakeElement()

    def timer(self, delay, callback, **kwargs):
        self.timers.append((delay, callback, kwargs))


@pytest.fixture
def picker_ui(monkeypatch):
    fake_ui = FakePickerUI()
    monkeypatch.setattr(picker_module, "ui", fake_ui)
    return fake_ui


def test_picker_constructs_combined_input_and_numeric_time_wheels(picker_ui) -> None:
    changed = []
    initial = datetime(2026, 10, 30, 11, 13, tzinfo=timezone.utc)

    picker = DateTimePicker("Observed at", initial, lambda: changed.append(True))

    assert picker.element.value == initial.astimezone().strftime("%Y-%m-%d %H:%M")
    assert picker.value == initial
    assert len(picker_ui.wheels) == 2
    assert picker_ui.labels[0].text == "HH"
    assert picker_ui.labels[25].text == "MM"
    assert [label.text for label in picker_ui.labels[1:25]] == [
        f"{hour:02d}" for hour in range(24)
    ]
    assert [label.text for label in picker_ui.labels[26:86]] == [
        f"{minute:02d}" for minute in range(60)
    ]
    assert changed == []


def test_wheel_clicks_update_input_once_and_programmatic_set_does_not_notify(
    picker_ui,
) -> None:
    changed = []
    picker = DateTimePicker(
        "Observed at",
        datetime(2026, 10, 30, 11, 13, tzinfo=timezone.utc),
        lambda: changed.append(picker.element.value),
    )
    current_hour = int(datetime(2026, 10, 30, 11, 13, tzinfo=timezone.utc)
                       .astimezone()
                       .strftime("%H"))
    next_hour = (current_hour + 1) % 24
    hour_label = picker_ui.labels[1 + next_hour]

    hour_label.events["click"]()
    hour_label.events["click"]()

    assert picker.element.value.endswith(f"{next_hour:02d}:13")
    assert changed == [picker.element.value]
    picker._set_hour(24)
    assert picker.element.value.endswith(f"{next_hour:02d}:13")

    next_value = datetime(2026, 11, 2, 8, 45, tzinfo=timezone.utc)
    picker.set_value(next_value)

    assert picker.value == next_value
    assert picker_ui.dates[0].value == next_value.astimezone().strftime("%Y-%m-%d")
    assert picker.element.updated > 0
    assert len(changed) == 1


def test_wheel_scroll_clamps_at_bounds_and_waits_until_centered(picker_ui) -> None:
    picker = DateTimePicker(
        "Observed at",
        datetime(2026, 10, 30, 11, 13, tzinfo=timezone.utc),
    )
    hour_wheel = picker_ui.wheels[0]
    initial_value = picker.element.value

    hour_wheel.on_scroll(SimpleNamespace(vertical_position=16))
    assert picker.element.value == initial_value

    picker._center_hour()
    delay, enable_wheel, options = picker_ui.timers[-1]
    assert delay == picker_module.TIME_WHEEL_SCROLL_SETTLE_SECONDS
    assert options == {"once": True, "immediate": False}
    enable_wheel()

    hour_wheel.on_scroll(SimpleNamespace(vertical_position=-1000))
    assert picker.element.value.endswith("00:13")
    hour_wheel.on_scroll(SimpleNamespace(vertical_position=5000))
    assert picker.element.value.endswith("23:13")

    picker._suspend_hour_scroll()
    suspended_value = picker.element.value
    hour_wheel.on_scroll(SimpleNamespace(vertical_position=16))
    assert picker.element.value == suspended_value


def test_open_menu_centers_time_wheels_after_delay(picker_ui) -> None:
    picker = DateTimePicker(
        "Observed at",
        datetime(2026, 10, 30, 11, 13, tzinfo=timezone.utc),
    )

    picker._open_menu()

    assert picker._menu.opened is True
    delay, center_wheels, options = picker_ui.timers[-1]
    assert delay == picker_module.TIME_WHEEL_OPEN_DELAY_SECONDS
    assert options == {"once": True, "immediate": False}
    center_wheels()
    assert len(picker_ui.timers) == 3
    assert all(
        timer[0] == picker_module.TIME_WHEEL_SCROLL_SETTLE_SECONDS
        for timer in picker_ui.timers[1:]
    )
    for _, enable_wheel, _ in picker_ui.timers[1:]:
        enable_wheel()


def test_date_change_syncs_and_date_only_picker_hides_time_controls(picker_ui) -> None:
    changed = []
    picker = DateTimePicker(
        "Date",
        datetime(2026, 10, 30, 11, 13, tzinfo=timezone.utc),
        lambda: changed.append(True),
        show_time=False,
    )
    assert picker.element.value == datetime(
        2026, 10, 30, 11, 13, tzinfo=timezone.utc
    ).astimezone().strftime("%Y-%m-%d")
    assert picker.value == datetime(2026, 10, 30).astimezone(timezone.utc)

    picker._date_picker.value = "2026-11-02"
    picker._handle_date_change(None)
    assert picker.element.value == "2026-11-02"
    assert changed == [True]

    picker._date_picker.value = None
    picker._handle_date_change(None)
    assert changed == [True]

    picker._open_menu()
    assert picker._menu.opened is True
    assert picker_ui.timers == []


@pytest.mark.parametrize(
    ("value", "show_time"),
    [
        ("not-a-date", True),
        ("2026-02-30 12:00", True),
        ("2026-10-30", True),
        ("2026-02-30", False),
        ("", False),
        (None, False),
    ],
)
def test_picker_rejects_malformed_or_missing_values(value, show_time) -> None:
    with pytest.raises(ValidationError):
        _parse_local_datetime_value(value, show_time=show_time)


def test_picker_parses_explicit_timezone_offsets_to_utc() -> None:
    assert _parse_local_datetime_value("2026-10-30T17:35:00+02:00") == datetime(
        2026, 10, 30, 15, 35, tzinfo=timezone.utc
    )
