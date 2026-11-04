from datetime import datetime, timedelta, timezone

import pytest

from aqman.ui.components.chart_axis import x_axis_date_format


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
