from datetime import date, datetime, timezone

from aqman.models import Fertilizer, FertilizerApplication
from aqman.services import DailyAquariumHistory
from aqman.ui.components.activity_history import ActivityHistory


def test_history_table_has_a_separate_column_for_each_fertilizer() -> None:
    nitrate = Fertilizer(id=4, name="Nitrate", dose_ml_per_100l=5)
    macro = Fertilizer(id=11, name="Macro", dose_ml_per_100l=10)
    first_application = FertilizerApplication(
        id=1,
        timestamp=datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc),
        aquarium_id=1,
        fertilizer_id=nitrate.id,
        actual_dose_ml=2.5,
        fertilizer=nitrate,
    )
    second_nitrate_application = FertilizerApplication(
        id=3,
        timestamp=datetime(2026, 10, 30, 18, 0, tzinfo=timezone.utc),
        aquarium_id=1,
        fertilizer_id=nitrate.id,
        actual_dose_ml=1,
        fertilizer=nitrate,
    )
    second_application = FertilizerApplication(
        id=2,
        timestamp=datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
        aquarium_id=1,
        fertilizer_id=macro.id,
        actual_dose_ml=4,
        fertilizer=macro,
    )
    first_day = DailyAquariumHistory(
        day=date(2026, 10, 30),
        measurements={},
        water_changes=(),
        notes=(),
        fertilizer_applications=(first_application, second_nitrate_application),
    )
    second_day = DailyAquariumHistory(
        day=date(2026, 10, 31),
        measurements={},
        water_changes=(),
        notes=(),
        fertilizer_applications=(second_application,),
    )
    history = ActivityHistory.__new__(ActivityHistory)
    history._language = "en"

    columns, parameter_ids, fertilizer_ids = history._history_columns(
        [first_day, second_day]
    )
    row = history._history_row(first_day, parameter_ids, fertilizer_ids)

    assert fertilizer_ids == [11, 4]
    assert [
        (column["name"], column["label"])
        for column in columns
        if column["name"].startswith("fertilizer_")
    ] == [
        ("fertilizer_11", "Macro"),
        ("fertilizer_4", "Nitrate"),
    ]
    assert all(
        "classes" not in column and "headerClasses" not in column
        for column in columns
        if column["name"].startswith("fertilizer_")
    )
    water_change_column = next(
        column for column in columns if column["name"] == "water_changes"
    )
    assert "classes" not in water_change_column
    assert "headerClasses" not in water_change_column
    assert row["fertilizer_4"] == [
        {"id": 1, "label": "2.5 ml"},
        {"id": 3, "label": "1 ml"},
    ]
    assert row["fertilizer_11"] == []
    assert "fertilizer_applications" not in row
