import math
from collections.abc import Mapping


NET_VOLUME_RATIO = 0.85
BASE_DOSE_VOLUME_LITERS = 100.0
DOSE_INCREMENT_ML = 0.1
DOSE_DECIMAL_PLACES = 1


def _positive_finite(value: float, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a number.") from error
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return number


def net_volume_liters(gross_volume_liters: float) -> float:
    gross_volume = _positive_finite(gross_volume_liters, "Gross aquarium volume")
    return gross_volume * NET_VOLUME_RATIO


def calculate_recommended_dose_ml(
    *,
    gross_volume_liters: float,
    dose_ml_per_100l: float,
    target_effect_ppm_per_dose: float,
    target_increase_ppm: float,
) -> float:
    net_volume = net_volume_liters(gross_volume_liters)
    base_dose = _positive_finite(dose_ml_per_100l, "Base dose")
    target_effect = _positive_finite(
        target_effect_ppm_per_dose,
        "Target parameter effect",
    )
    target_increase = _positive_finite(target_increase_ppm, "Target increase")
    base_dose_for_aquarium = base_dose * net_volume / BASE_DOSE_VOLUME_LITERS
    recommended_dose = target_increase * base_dose_for_aquarium / target_effect
    rounded_dose = round(recommended_dose, DOSE_DECIMAL_PLACES)
    if rounded_dose < DOSE_INCREMENT_ML:
        raise ValueError("Calculated dose is below 0.1 ml and cannot be rounded safely.")
    return rounded_dose


def calculate_predicted_effects(
    *,
    gross_volume_liters: float,
    dose_ml_per_100l: float,
    actual_dose_ml: float,
    effects: Mapping[int, float],
) -> dict[int, float]:
    net_volume = net_volume_liters(gross_volume_liters)
    base_dose = _positive_finite(dose_ml_per_100l, "Base dose")
    actual_dose = _positive_finite(actual_dose_ml, "Actual dose")
    base_dose_for_aquarium = base_dose * net_volume / BASE_DOSE_VOLUME_LITERS
    dose_ratio = actual_dose / base_dose_for_aquarium
    return {
        parameter_id: _positive_finite(effect, "Fertilizer effect") * dose_ratio
        for parameter_id, effect in effects.items()
    }
