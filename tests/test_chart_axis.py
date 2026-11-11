from datetime import datetime, timedelta, timezone

import pytest

from aqman.ui.components.chart_axis import (
    format_tooltip_datetime,
    x_axis_date_format,
)


@pytest.mark.parametrize(
    ("show_time", "expected_format"),
    [
        (True, "%Y-%m-%d %H:%M"),
        (False, "%Y-%m-%d"),
    ],
)
def test_tooltip_datetime_format_respects_time_setting(
    show_time: bool,
    expected_format: str,
) -> None:
    value = datetime(2026, 10, 1, 12, 30, tzinfo=timezone.utc)

    assert format_tooltip_datetime(value, show_time) == (
        value.astimezone().strftime(expected_format)
    )


@pytest.mark.parametrize(
    ("duration", "expected_format"),
    [
        (timedelta(days=1), "{MM}-{dd} {HH}:{mm}"),
        (timedelta(days=14), "{MM}-{dd}"),
        (timedelta(days=90), "{yyyy}-{MM}-{dd}"),
    ],
)
def test_x_axis_date_format_adapts_to_selected_range(
    duration: timedelta,
    expected_format: str,
) -> None:
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)

    assert x_axis_date_format(start, start + duration) == expected_format
