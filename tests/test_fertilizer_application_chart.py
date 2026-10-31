from datetime import datetime, timezone

from aqman.models import Fertilizer, FertilizerApplication
from aqman.ui.components.fertilizer_application_chart import (
    _fertilizer_application_chart_options,
)


def test_fertilizer_application_chart_shows_separate_discrete_fertilizer_series() -> None:
    first_timestamp = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    second_timestamp = datetime(2026, 10, 31, 15, 30, tzinfo=timezone.utc)
    nitro = Fertilizer(id=2, name="Nitro", dose_ml_per_100l=10)
    potassium = Fertilizer(id=1, name="Potassium", dose_ml_per_100l=5)
    applications = [
        FertilizerApplication(
            id=1,
            timestamp=first_timestamp,
            fertilizer=nitro,
            actual_dose_ml=4.5,
        ),
        FertilizerApplication(
            id=2,
            timestamp=second_timestamp,
            fertilizer=potassium,
            actual_dose_ml=2,
        ),
        FertilizerApplication(
            id=3,
            timestamp=second_timestamp,
            fertilizer=nitro,
            actual_dose_ml=5,
        ),
    ]

    options = _fertilizer_application_chart_options(applications, "Dose (ml)")

    assert options["xAxis"]["type"] == "time"
    assert options["yAxis"]["name"] == "Dose (ml)"
    assert [series["name"] for series in options["series"]] == [
        "Nitro",
        "Potassium",
    ]
    assert all(series["type"] == "scatter" for series in options["series"])
    assert all("lineStyle" not in series for series in options["series"])
    assert options["series"][0]["data"] == [
        {
            "name": first_timestamp.astimezone().strftime("%Y-%m-%d %H:%M"),
            "value": [int(first_timestamp.timestamp() * 1000), 4.5],
        },
        {
            "name": second_timestamp.astimezone().strftime("%Y-%m-%d %H:%M"),
            "value": [int(second_timestamp.timestamp() * 1000), 5],
        },
    ]
    assert options["series"][1]["data"][0]["value"] == [
        int(second_timestamp.timestamp() * 1000),
        2,
    ]
