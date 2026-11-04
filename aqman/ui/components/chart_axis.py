from datetime import datetime, timedelta, timezone


def x_axis_date_format(start: datetime, end: datetime) -> str:
    duration = end.astimezone(timezone.utc) - start.astimezone(timezone.utc)
    if duration <= timedelta(days=2):
        return "{MM}-{dd} {HH}:{mm}"
    if duration <= timedelta(days=31):
        return "{MM}-{dd}"
    return "{yyyy}-{MM}-{dd}"
