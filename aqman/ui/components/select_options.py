from collections.abc import Mapping


def retain_or_first_option(
    current_value: object,
    options: Mapping[int, object],
) -> int | None:
    try:
        current_id = int(current_value)
    except (TypeError, ValueError):
        current_id = None
    return current_id if current_id in options else next(iter(options), None)
