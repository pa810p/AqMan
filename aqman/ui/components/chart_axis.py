from datetime import datetime, timedelta, timezone


def format_tooltip_datetime(value: datetime, show_time: bool = True) -> str:
    local_value = value.astimezone()
    date_format = "%Y-%m-%d %H:%M" if show_time else "%Y-%m-%d"
    return local_value.strftime(date_format)


def x_axis_date_format(start: datetime, end: datetime) -> str:
    duration = end.astimezone(timezone.utc) - start.astimezone(timezone.utc)
    if duration <= timedelta(days=2):
        return "{MM}-{dd} {HH}:{mm}"
    if duration <= timedelta(days=31):
        return "{MM}-{dd}"
    return "{yyyy}-{MM}-{dd}"
