from datetime import datetime, timezone
from unittest.mock import Mock

from aqman.models import Fertilizer, FertilizerApplication
from aqman.ui.components import fertilizer_application_chart as chart_module
from aqman.ui.components.fertilizer_application_chart import (
    FertilizerApplicationChart,
    _fertilizer_application_chart_options,
)


class FakeElement:
    def __init__(self):
        self.visible = None
        self.text = ""
        self.options = {}
        self.updated = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def classes(self, _):
        return self

    def set_visibility(self, visible):
        self.visible = visible

    def set_text(self, text):
        self.text = text

    def update(self):
        self.updated += 1


class FakeChartUI:
    def __init__(self):
        self.chart = FakeElement()
        self.labels = []

    def card(self):
        return FakeElement()

    def label(self, _text=""):
        label = FakeElement()
        self.labels.append(label)
        return label

    def echart(self, options):
        self.chart.options = options
        return self.chart


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


def test_chart_refresh_and_clear_manage_empty_and_populated_states(monkeypatch) -> None:
    fake_ui = FakeChartUI()
    monkeypatch.setattr(chart_module, "ui", fake_ui)
    service = Mock()
    chart = FertilizerApplicationChart(service, "en")
    start = datetime(2026, 10, 1, tzinfo=timezone.utc)
    end = datetime(2026, 11, 1, tzinfo=timezone.utc)

    service.fertilizer_applications_in_range.return_value = []
    chart.refresh(4, start, end)

    service.fertilizer_applications_in_range.assert_called_once_with(4, start, end)
    assert fake_ui.chart.visible is True
    assert fake_ui.chart.options["series"] == []
    assert chart._status.text == (
        "No fertilizer applications match this date range."
    )
    assert chart._status.visible is True

    fertilizer = Fertilizer(id=6, name="Trace", dose_ml_per_100l=2)
    application = FertilizerApplication(
        id=9,
        timestamp=start,
        aquarium_id=4,
        fertilizer_id=6,
        actual_dose_ml=1.25,
        fertilizer=fertilizer,
    )
    service.fertilizer_applications_in_range.return_value = [application]
    chart.refresh(4, start, end)

    assert chart._status.text == ""
    assert chart._status.visible is False
    assert fake_ui.chart.visible is True
    assert fake_ui.chart.options["series"][0]["name"] == "Trace"
    assert fake_ui.chart.options["series"][0]["data"][0]["value"] == [
        int(start.timestamp() * 1000),
        1.25,
    ]

    chart.clear()

    assert fake_ui.chart.options == {}
    assert fake_ui.chart.visible is False
    assert chart._status.visible is False
