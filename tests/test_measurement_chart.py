from datetime import datetime, timezone

import pytest

from aqman.models import Measurement, Parameter
from aqman.ui.components.measurement_chart import (
    _calendar_month_before,
    _default_chart_range,
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
    assert options["series"][0]["data"] == [
        [int(measurement.timestamp.timestamp() * 1000), measurement.value]
        for measurement in measurements
    ]
