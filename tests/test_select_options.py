import pytest

from aqman.ui.components.select_options import retain_or_first_option


@pytest.mark.parametrize(
    ("current_value", "options", "expected"),
    [
        ("2", {1: "One", 2: "Two"}, 2),
        ("invalid", {1: "One", 2: "Two"}, 1),
        (99, {1: "One", 2: "Two"}, 1),
        (None, {}, None),
    ],
)
def test_retain_or_first_option(current_value, options, expected) -> None:
    assert retain_or_first_option(current_value, options) == expected
