from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from aqman.models import Measurement, Parameter
from aqman.services import ValidationError
from aqman.ui.components import aquarium_charts as aquarium_charts_module
from aqman.ui.components import measurement_chart as measurement_chart_module
from aqman.ui.components.aquarium_charts import (
    AquariumCharts,
    _calendar_month_before,
    _default_chart_range,
    _end_of_local_day,
)
from aqman.ui.components.measurement_chart import (
    MeasurementChart,
    _measurement_chart_options,
)


class FakeElement:
    def __init__(self, value=None, options=None):
        self.value = value
        self.options = options or {}
        self.visible = None
        self.text = ""
        self.updated = 0
        self._value_change = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def classes(self, _):
        return self

    def update(self):
        self.updated += 1

    def set_visibility(self, visible):
        self.visible = visible

    def set_text(self, text):
        self.text = text

    def on_value_change(self, callback):
        self._value_change = callback


class FakeChartUI:
    def __init__(self):
        self.selects = []
        self.charts = []
        self.labels = []

    def card(self):
        return FakeElement()

    def row(self):
        return FakeElement()

    def column(self):
        return FakeElement()

    def label(self, _text=""):
        label = FakeElement()
        self.labels.append(label)
        return label

    def select(self, options, label):
        select = FakeElement(options=options)
        select.label = label
        self.selects.append(select)
        return select

    def echart(self, options):
        chart = FakeElement(options=options)
        self.charts.append(chart)
        return chart


class BrokenPicker:
    @property
    def value(self):
        raise ValidationError("bad date")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime(2026, 3, 31, 10, 15), datetime(2026, 2, 28, 10, 15)),
        (datetime(2024, 3, 31, 10, 15), datetime(2024, 2, 29, 10, 15)),
        (datetime(2026, 1, 31, 10, 15), datetime(2025, 12, 31, 10, 15)),
    ],
)
def test_calendar_month_subtraction_clamps_to_target_month(
    value: datetime,
    expected: datetime,
) -> None:
    assert _calendar_month_before(value) == expected


def test_default_chart_range_ends_now_and_starts_one_calendar_month_before() -> None:
    now = datetime(2026, 3, 31, 10, 15, 42, tzinfo=timezone.utc)

    start, end = _default_chart_range(now)

    expected_end = now.astimezone().replace(second=0, microsecond=0)
    assert start == _calendar_month_before(expected_end.replace(tzinfo=None))
    assert end == expected_end


def test_date_only_chart_end_includes_the_entire_local_day() -> None:
    local_midnight = datetime(2026, 10, 31).astimezone(timezone.utc)

    end = _end_of_local_day(local_midnight)

    local_end = end.astimezone()
    assert local_end.date() == local_midnight.astimezone().date()
    assert local_end.strftime("%H:%M:%S.%f") == "23:59:59.999999"


def test_measurement_chart_options_show_iso_dates_and_parameter_units() -> None:
    parameter = Parameter(name="NO3", unit="mg/L")
    measurements = [
        Measurement(
            timestamp=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
            value=5.0,
        ),
        Measurement(
            timestamp=datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
            value=7.5,
        ),
    ]

    options = _measurement_chart_options(parameter, measurements)

    assert options["xAxis"]["type"] == "time"
    assert options["xAxis"]["axisLabel"]["formatter"] == "{yyyy}-{MM}-{dd}"
    assert options["yAxis"]["name"] == "NO3 (mg/L)"
    assert options["tooltip"]["trigger"] == "item"
    assert options["series"][0]["type"] == "scatter"
    assert options["series"][0]["symbol"] == "circle"
    assert "lineStyle" not in options["series"][0]
    assert options["series"][0]["data"] == [
        [int(measurement.timestamp.timestamp() * 1000), measurement.value]
        for measurement in measurements
    ]


def test_parameter_change_refreshes_only_the_measurement_chart() -> None:
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, tzinfo=timezone.utc)
    charts = AquariumCharts.__new__(AquariumCharts)
    charts._language = "en"
    charts._aquarium_id_provider = lambda: 7
    charts._show_time = True
    charts._start = SimpleNamespace(value=start)
    charts._end = SimpleNamespace(value=end)
    charts._range_status = Mock()
    charts._measurement_chart = Mock()
    charts._fertilizer_chart = Mock()

    charts.refresh_measurement_chart()

    charts._measurement_chart.refresh.assert_called_once_with(7, start, end)
    charts._fertilizer_chart.refresh.assert_not_called()


def test_aquarium_charts_builds_shared_pickers_and_initializes_range(
    monkeypatch,
) -> None:
    fake_ui = FakeChartUI()
    monkeypatch.setattr(aquarium_charts_module, "ui", fake_ui)
    picker_instances = []

    class Picker:
        def __init__(self, label, on_change, show_time):
            self.label = label
            self.on_change = on_change
            self.show_time = show_time
            self.value = None
            self.element = FakeElement()
            self.set_values = []
            picker_instances.append(self)

        def set_value(self, value):
            self.value = value
            self.set_values.append(value)

    class Measurement:
        def __init__(self, *_args):
            pass

    class Fertilizer:
        def __init__(self, *_args):
            pass

    monkeypatch.setattr(aquarium_charts_module, "DateTimePicker", Picker)
    monkeypatch.setattr(aquarium_charts_module, "MeasurementChart", Measurement)
    monkeypatch.setattr(
        aquarium_charts_module, "FertilizerApplicationChart", Fertilizer
    )
    now = datetime(2026, 3, 31, 10, 15, 42, tzinfo=timezone.utc)
    expected_end = now.replace(second=0, microsecond=0)
    monkeypatch.setattr(
        aquarium_charts_module,
        "_default_chart_range",
        lambda: (
            _calendar_month_before(expected_end.replace(tzinfo=None)),
            expected_end,
        ),
    )

    charts = AquariumCharts(Mock(), lambda: 5, "en", show_time=False)

    assert [picker.label for picker in picker_instances] == ["Start", "End"]
    assert all(picker.show_time is False for picker in picker_instances)
    assert all(picker.on_change == charts.refresh for picker in picker_instances)
    assert picker_instances[0].value == datetime(2026, 2, 28, 10, 15)
    assert picker_instances[1].value == datetime(
        2026, 3, 31, 10, 15, tzinfo=timezone.utc
    )


def test_aquarium_charts_refreshes_both_components_for_a_valid_range() -> None:
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 31, tzinfo=timezone.utc)
    charts = AquariumCharts.__new__(AquariumCharts)
    charts._language = "en"
    charts._aquarium_id_provider = lambda: 7
    charts._show_time = True
    charts._start = SimpleNamespace(value=start)
    charts._end = SimpleNamespace(value=end)
    charts._range_status = Mock()
    charts._measurement_chart = Mock()
    charts._fertilizer_chart = Mock()

    charts.refresh()

    charts._measurement_chart.refresh.assert_called_once_with(7, start, end)
    charts._fertilizer_chart.refresh.assert_called_once_with(7, start, end)
    charts._range_status.set_visibility.assert_called_once_with(False)


@pytest.mark.parametrize(
    ("provider", "start_value", "end_value", "status_text", "reset_parameter"),
    [
        (
            lambda: (_ for _ in ()).throw(ValidationError("missing aquarium")),
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            datetime(2026, 10, 31, tzinfo=timezone.utc),
            "Select an aquarium to view its charts.",
            True,
        ),
        (
            lambda: 7,
            None,
            datetime(2026, 10, 31, tzinfo=timezone.utc),
            "Enter valid start and end dates and times.",
            False,
        ),
        (
            lambda: 7,
            datetime(2026, 10, 31, tzinfo=timezone.utc),
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            "The start date and time must not be after the end.",
            False,
        ),
    ],
)
def test_aquarium_charts_clears_and_reports_invalid_ranges(
    provider,
    start_value,
    end_value,
    status_text,
    reset_parameter,
) -> None:
    charts = AquariumCharts.__new__(AquariumCharts)
    charts._language = "en"
    charts._aquarium_id_provider = provider
    charts._show_time = True
    charts._start = SimpleNamespace(value=start_value)
    charts._end = SimpleNamespace(value=end_value)
    charts._range_status = Mock()
    charts._measurement_chart = Mock()
    charts._fertilizer_chart = Mock()

    if start_value is None:
        charts._start = BrokenPicker()

    charts.refresh()

    charts._measurement_chart.clear.assert_called_once_with(
        reset_parameter=reset_parameter
    )
    charts._fertilizer_chart.clear.assert_called_once_with()
    charts._range_status.set_text.assert_called_once_with(status_text)
    charts._range_status.set_visibility.assert_called_once_with(True)
    charts._measurement_chart.refresh.assert_not_called()
    charts._fertilizer_chart.refresh.assert_not_called()


def test_date_only_range_extends_end_and_measurement_refresh_is_independent() -> None:
    start = datetime(2026, 10, 1).astimezone(timezone.utc)
    end = datetime(2026, 10, 31).astimezone(timezone.utc)
    charts = AquariumCharts.__new__(AquariumCharts)
    charts._language = "en"
    charts._aquarium_id_provider = lambda: 7
    charts._show_time = False
    charts._start = SimpleNamespace(value=start)
    charts._end = SimpleNamespace(value=end)
    charts._range_status = Mock()
    charts._measurement_chart = Mock()
    charts._fertilizer_chart = Mock()

    charts.refresh_measurement_chart()

    charts._measurement_chart.refresh.assert_called_once_with(
        7, start, _end_of_local_day(end)
    )
    charts._fertilizer_chart.refresh.assert_not_called()


@pytest.mark.parametrize(
    ("provider", "start", "end", "expected_status", "clear_with_reset"),
    [
        (
            lambda: (_ for _ in ()).throw(ValidationError("missing aquarium")),
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            datetime(2026, 10, 31, tzinfo=timezone.utc),
            "Select an aquarium to view its charts.",
            True,
        ),
        (
            lambda: 7,
            BrokenPicker(),
            datetime(2026, 10, 31, tzinfo=timezone.utc),
            "Enter valid start and end dates and times.",
            False,
        ),
        (
            lambda: 7,
            datetime(2026, 10, 31, tzinfo=timezone.utc),
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            "The start date and time must not be after the end.",
            False,
        ),
    ],
)
def test_measurement_only_refresh_handles_invalid_context_and_range(
    provider,
    start,
    end,
    expected_status,
    clear_with_reset,
) -> None:
    charts = AquariumCharts.__new__(AquariumCharts)
    charts._language = "en"
    charts._aquarium_id_provider = provider
    charts._show_time = True
    charts._start = SimpleNamespace(value=start) if not isinstance(start, BrokenPicker) else start
    charts._end = SimpleNamespace(value=end)
    charts._range_status = Mock()
    charts._measurement_chart = Mock()
    charts._fertilizer_chart = Mock()

    charts.refresh_measurement_chart()

    if clear_with_reset:
        charts._measurement_chart.clear.assert_called_once_with(reset_parameter=True)
    else:
        charts._measurement_chart.clear.assert_called_once_with()
    charts._range_status.set_text.assert_called_once_with(expected_status)
    charts._range_status.set_visibility.assert_called_once_with(True)
    charts._measurement_chart.refresh.assert_not_called()
    charts._fertilizer_chart.clear.assert_not_called()
    charts._fertilizer_chart.refresh.assert_not_called()


def test_measurement_chart_refresh_selects_parameters_and_renders_data(
    monkeypatch,
) -> None:
    fake_ui = FakeChartUI()
    monkeypatch.setattr(measurement_chart_module, "ui", fake_ui)
    changed = Mock()
    service = Mock()
    parameter = Parameter(id=4, name="NO3", unit="mg/L")
    other_parameter = Parameter(id=7, name="pH", unit="pH")
    measurement = Measurement(
        id=1,
        aquarium_id=9,
        parameter_id=4,
        timestamp=datetime(2026, 10, 20, 12, tzinfo=timezone.utc),
        value=6.5,
    )
    service.measured_parameters.return_value = [parameter, other_parameter]
    service.measurements_in_range.return_value = [measurement]
    chart = MeasurementChart(service, "en", changed)
    chart._parameter.value = "7"
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    end = datetime(2026, 11, 1, tzinfo=timezone.utc)

    chart.refresh(9, start, end)

    service.measured_parameters.assert_called_once_with(9)
    service.measurements_in_range.assert_called_once_with(9, 7, start, end)
    assert chart._parameter.options == {4: "NO3 (mg/L)", 7: "pH (pH)"}
    assert chart._parameter.value == 7
    assert chart._chart.visible is True
    assert chart._status.visible is False
    chart._parameter._value_change(None)
    changed.assert_called_once_with()


@pytest.mark.parametrize("old_value", ["not-an-id", None, "99"])
def test_measurement_chart_falls_back_to_first_available_parameter(
    monkeypatch,
    old_value,
) -> None:
    fake_ui = FakeChartUI()
    monkeypatch.setattr(measurement_chart_module, "ui", fake_ui)
    service = Mock()
    parameter = Parameter(id=4, name="NO3", unit="mg/L")
    service.measured_parameters.return_value = [parameter]
    service.measurements_in_range.return_value = []
    chart = MeasurementChart(service, "en", lambda: None)
    chart._parameter.value = old_value

    chart.refresh(
        9,
        datetime(2026, 10, 1, tzinfo=timezone.utc),
        datetime(2026, 11, 1, tzinfo=timezone.utc),
    )

    assert chart._parameter.value == 4
    assert chart._chart.visible is True
    assert chart._status.text == (
        "No measurements match this parameter and date range."
    )
    assert chart._status.visible is True
    assert chart._chart.options["series"][0]["data"] == []


def test_measurement_chart_handles_missing_parameters_and_invalid_query(
    monkeypatch,
) -> None:
    fake_ui = FakeChartUI()
    monkeypatch.setattr(measurement_chart_module, "ui", fake_ui)
    service = Mock()
    chart = MeasurementChart(service, "en", lambda: None)
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    end = datetime(2026, 11, 1, tzinfo=timezone.utc)
    service.measured_parameters.return_value = []

    chart.refresh(9, start, end)

    assert chart._chart.options == {}
    assert chart._chart.visible is False
    assert chart._status.text == (
        "No measurements are available to plot for this aquarium."
    )
    assert chart._status.visible is True
    service.measurements_in_range.assert_not_called()

    service.measured_parameters.return_value = [Parameter(id=1, name="pH", unit="pH")]
    service.measurements_in_range.side_effect = ValidationError("invalid range")
    chart.refresh(9, start, end)

    assert chart._chart.options == {}
    assert chart._chart.visible is False
    assert chart._status.text == "Enter valid start and end dates and times."
    assert chart._status.visible is True


def test_measurement_chart_clear_can_reset_the_parameter(monkeypatch) -> None:
    fake_ui = FakeChartUI()
    monkeypatch.setattr(measurement_chart_module, "ui", fake_ui)
    chart = MeasurementChart(Mock(), "en", lambda: None)
    chart._parameter.options = {4: "NO3 (mg/L)"}
    chart._parameter.value = 4
    chart._chart.options = {"series": ["old"]}

    chart.clear(reset_parameter=True)

    assert chart._parameter.options == {}
    assert chart._parameter.value is None
    assert chart._parameter.updated == 1
    assert chart._chart.options == {}
    assert chart._chart.visible is False
    assert chart._status.visible is False
