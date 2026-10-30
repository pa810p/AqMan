import pytest

from aqman.fertilizer_calculations import (
    calculate_predicted_effects,
    calculate_recommended_dose_ml,
)


def test_recommended_dose_uses_net_volume_and_rounds_to_tenth() -> None:
    gross_volume_liters = 180 / 0.85

    dose = calculate_recommended_dose_ml(
        gross_volume_liters=gross_volume_liters,
        dose_ml_per_100l=10,
        target_effect_ppm_per_dose=10,
        target_increase_ppm=5,
    )

    assert dose == 9.0


def test_effect_preview_uses_actual_dose() -> None:
    predicted = calculate_predicted_effects(
        gross_volume_liters=180 / 0.85,
        dose_ml_per_100l=10,
        actual_dose_ml=9,
        effects={1: 10, 2: 1.5},
    )

    assert predicted == {1: 5.0, 2: 0.75}


@pytest.mark.parametrize(
    ("gross_volume", "dose", "target_effect", "target_increase"),
    [
        (0, 10, 10, 5),
        (180, 0, 10, 5),
        (180, 10, 0, 5),
        (180, 10, 10, 0),
        (180, 10, 10, float("nan")),
        (float("inf"), 10, 10, 5),
    ],
)
def test_recommended_dose_rejects_invalid_inputs(
    gross_volume: float,
    dose: float,
    target_effect: float,
    target_increase: float,
) -> None:
    with pytest.raises(ValueError):
        calculate_recommended_dose_ml(
            gross_volume_liters=gross_volume,
            dose_ml_per_100l=dose,
            target_effect_ppm_per_dose=target_effect,
            target_increase_ppm=target_increase,
        )


def test_recommended_dose_rejects_result_rounding_to_zero() -> None:
    with pytest.raises(ValueError, match="below 0.1 ml"):
        calculate_recommended_dose_ml(
            gross_volume_liters=100,
            dose_ml_per_100l=1,
            target_effect_ppm_per_dose=1000,
            target_increase_ppm=1,
        )


def test_effect_preview_rejects_non_positive_actual_dose() -> None:
    with pytest.raises(ValueError):
        calculate_predicted_effects(
            gross_volume_liters=180,
            dose_ml_per_100l=10,
            actual_dose_ml=0,
            effects={1: 10},
        )
