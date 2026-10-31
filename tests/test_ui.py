from datetime import datetime, timezone

import pytest

from aqman.services import ValidationError
from aqman.models import Measurement, Parameter
from aqman.ui import (
    _calendar_month_before,
    _default_chart_range,
    _format_datetime,
    _local_datetime_input_value,
    _local_datetime_parts,
    _measurement_chart_options,
    _parse_local_datetime,
    _parse_local_datetime_value,
)


def test_local_datetime_parts_use_24_hour_time() -> None:
    value = datetime(2026, 10, 30, 17, 35, tzinfo=timezone.utc)

    date_value, time_value = _local_datetime_parts(value)

    assert date_value == value.astimezone().strftime("%Y-%m-%d")
    assert time_value == value.astimezone().strftime("%H:%M")
    assert len(time_value) == 5


def test_parse_local_datetime_converts_local_time_to_utc() -> None:
    expected = datetime(2026, 10, 30, 17, 35).astimezone(timezone.utc)

    assert _parse_local_datetime("2026-10-30", "17:35") == expected


def test_combined_datetime_input_uses_iso_value() -> None:
    value = datetime(2026, 10, 31, 10, 45, tzinfo=timezone.utc)

    assert _local_datetime_input_value(value) == value.astimezone().strftime(
        "%Y-%m-%d %H:%M"
    )


def test_parse_combined_datetime_input_converts_local_time_to_utc() -> None:
    expected = datetime(2026, 10, 30, 17, 35).astimezone(timezone.utc)

    assert _parse_local_datetime_value("2026-10-30 17:35") == expected


@pytest.mark.parametrize("value", [None, "", "2026-10-30", "30-10-2026 17:35"])
def test_parse_combined_datetime_input_rejects_missing_or_invalid_values(
    value: str | None,
) -> None:
    with pytest.raises(ValidationError):
        _parse_local_datetime_value(value)


def test_format_datetime_uses_iso_date_order() -> None:
    value = datetime(2026, 10, 30, 17, 35, tzinfo=timezone.utc)

    assert _format_datetime(value, "en") == value.astimezone().strftime("%Y-%m-%d %H:%M")


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


@pytest.mark.parametrize(
    ("date_value", "time_value"),
    [
        ("", "17:35"),
        ("2026-10-30", ""),
        ("30-10-2026", "17:35"),
        ("2026-10-30", "25:00"),
        ("2026-02-30", "17:35"),
    ],
)
def test_parse_local_datetime_rejects_missing_or_invalid_values(
    date_value: str,
    time_value: str,
) -> None:
    with pytest.raises(ValidationError):
        _parse_local_datetime(date_value, time_value)
