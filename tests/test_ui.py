from datetime import datetime, timezone

import pytest

from aqman.services import ValidationError
from aqman.ui import (
    _format_datetime,
)
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
