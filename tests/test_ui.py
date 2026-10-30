from datetime import datetime, timezone

import pytest

from aqman.services import ValidationError
from aqman.ui import _local_datetime_parts, _parse_local_datetime


def test_local_datetime_parts_use_24_hour_time() -> None:
    value = datetime(2026, 10, 30, 17, 35, tzinfo=timezone.utc)

    date_value, time_value = _local_datetime_parts(value)

    assert date_value == value.astimezone().strftime("%Y-%m-%d")
    assert time_value == value.astimezone().strftime("%H:%M")
    assert len(time_value) == 5


def test_parse_local_datetime_converts_local_time_to_utc() -> None:
    expected = datetime(2026, 10, 30, 17, 35).astimezone(timezone.utc)

    assert _parse_local_datetime("2026-10-30", "17:35") == expected


@pytest.mark.parametrize(
    ("date_value", "time_value"),
    [
        ("", "17:35"),
        ("2026-10-30", ""),
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
