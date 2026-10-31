from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from aqman.models import Measurement, Parameter
from aqman.ui.components.aquarium_charts import (
    AquariumCharts,
    _calendar_month_before,
    _default_chart_range,
    _end_of_local_day,
)
from aqman.ui.components.measurement_chart import (
    _measurement_chart_options,
)


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
