from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from nicegui import ui

from aqman.fertilizer_calculations import (
    calculate_predicted_effects,
    calculate_recommended_dose_ml,
    net_volume_liters,
)
from aqman.models import Aquarium, Fertilizer
from aqman.services import (
    AquariumService,
    NotFoundError,
    ValidationError,
)
from aqman.translations import translate
from aqman.ui.components.date_time_picker import DateTimePicker

_SUBSCRIPT_DIGITS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


@dataclass(frozen=True)
class FertilizerApplicationValues:
    timestamp: datetime
    fertilizer_id: int
    actual_dose_ml: float
    notes: str | None


def _format_parameter_name(name: str) -> str:
    return name.translate(_SUBSCRIPT_DIGITS)


class FertilizerApplicationForm:
    def __init__(
        self,
        aquarium_service: AquariumService,
        aquarium_id_provider: Callable[[], int],
        language: str,
        on_save: Callable[[FertilizerApplicationForm], None],
        show_time: bool = True,
    ) -> None:
        self._aquarium_service = aquarium_service
        self._aquarium_id_provider = aquarium_id_provider
        self._language = language
        self._on_save = on_save
        self._fertilizers: dict[int, Fertilizer] = {}

        with ui.card().classes("w-full"):
            ui.label(self._t("new_fertilizer_application")).classes("text-h6")
            self._datetime = DateTimePicker(
                self._t("date_time"),
                show_time=show_time,
            )
            self._fertilizer = ui.select(
                {},
                label=self._t("fertilizer"),
            ).classes("w-full")
            self._target_parameter = ui.select(
                {},
                label=self._t("fertilizer_target_parameter"),
            ).classes("w-full")
            self._target_increase = ui.number(
                self._t("fertilizer_target_increase"),
                value=5,
                min=0.1,
            ).classes("w-full")
            self._recommended_dose = ui.label(
                self._t("fertilizer_dose_unavailable")
            ).classes("text-body2")
            self._actual_dose = ui.number(
                self._t("fertilizer_actual_dose"),
                min=0,
            ).classes("w-full")
            self._target_effect_preview = ui.label("—").classes("text-body2")
            self._other_effects = ui.label(
                self._t("fertilizer_effects_unavailable")
            ).classes("text-body2")
            self._notes = ui.textarea(self._t("optional_note")).classes("w-full")
            ui.button(
                self._t("save_fertilizer_application"),
                icon="save",
                on_click=lambda: self._on_save(self),
            )

        self._fertilizer.on_value_change(lambda _: self._refresh_parameters())
        self._target_parameter.on_value_change(
            lambda _: self._refresh_recommendation()
        )
        self._target_increase.on_value_change(
            lambda _: self._refresh_recommendation()
        )
        self._actual_dose.on_value_change(
            lambda _: self._refresh_effect_preview()
        )

    @property
    def values(self) -> FertilizerApplicationValues:
        try:
            fertilizer_id = int(self._fertilizer.value)
        except (TypeError, ValueError) as error:
            raise ValidationError("Select a fertilizer first.") from error
        actual_dose_ml = self._actual_dose.value
        if actual_dose_ml is None:
            raise ValidationError("Actual fertilizer dose must be a number.")
        return FertilizerApplicationValues(
            timestamp=self._datetime.value,
            fertilizer_id=fertilizer_id,
            actual_dose_ml=actual_dose_ml,
            notes=self._notes.value,
        )

    def set_fertilizers(self, fertilizers: list[Fertilizer]) -> None:
        self._fertilizers = {fertilizer.id: fertilizer for fertilizer in fertilizers}
        fertilizer_options = {
            fertilizer.id: fertilizer.name for fertilizer in fertilizers
        }
        try:
            previous_fertilizer_id = int(self._fertilizer.value)
        except (TypeError, ValueError):
            previous_fertilizer_id = None
        self._fertilizer.options = fertilizer_options
        self._fertilizer.value = (
            previous_fertilizer_id
            if previous_fertilizer_id in fertilizer_options
            else next(iter(fertilizer_options), None)
        )
        self._fertilizer.update()
        self._refresh_parameters()

    def reset_after_save(self) -> None:
        self._notes.value = ""
        self._datetime.set_value(datetime.now().astimezone())

    def _refresh_parameters(self) -> None:
        fertilizer = self._selected_fertilizer()
        effect_options = (
            {
                effect.parameter_id: (
                    f"{effect.parameter.name} ({effect.parameter.unit})"
                )
                for effect in fertilizer.effects
            }
            if fertilizer is not None
            else {}
        )
        try:
            previous_parameter_id = int(self._target_parameter.value)
        except (TypeError, ValueError):
            previous_parameter_id = None
        self._target_parameter.options = effect_options
        self._target_parameter.value = (
            previous_parameter_id
            if previous_parameter_id in effect_options
            else next(iter(effect_options), None)
        )
        self._target_parameter.update()
        self._refresh_recommendation()

    def _selected_fertilizer(self) -> Fertilizer | None:
        try:
            fertilizer_id = int(self._fertilizer.value)
        except (TypeError, ValueError):
            return None
        return self._fertilizers.get(fertilizer_id)

    def _current_aquarium(self) -> Aquarium:
        aquarium_id = self._aquarium_id_provider()
        aquarium = next(
            (
                item
                for item in self._aquarium_service.list_aquariums()
                if item.id == aquarium_id
            ),
            None,
        )
        if aquarium is None:
            raise NotFoundError("Aquarium not found.")
        return aquarium

    def _refresh_recommendation(self) -> None:
        fertilizer = self._selected_fertilizer()
        if fertilizer is None:
            self._recommended_dose.text = self._t("fertilizer_dose_unavailable")
            self._actual_dose.value = None
            self._actual_dose.update()
            self._refresh_effect_preview()
            return
        try:
            aquarium = self._current_aquarium()
            target_parameter_id = int(self._target_parameter.value)
            target_effect = next(
                effect
                for effect in fertilizer.effects
                if effect.parameter_id == target_parameter_id
            )
            recommended_dose = calculate_recommended_dose_ml(
                gross_volume_liters=aquarium.volume_liters,
                dose_ml_per_100l=fertilizer.dose_ml_per_100l,
                target_effect_ppm_per_dose=target_effect.ppm_per_dose,
                target_increase_ppm=self._target_increase.value,
            )
            net_volume = net_volume_liters(aquarium.volume_liters)
        except (StopIteration, TypeError, ValueError, ValidationError, NotFoundError):
            self._recommended_dose.text = self._t("fertilizer_dose_unavailable")
            self._actual_dose.value = None
            self._actual_dose.update()
            self._refresh_effect_preview()
            return
        self._recommended_dose.text = self._t(
            "fertilizer_recommended_dose",
            dose=recommended_dose,
            net_volume=net_volume,
        )
        self._actual_dose.value = recommended_dose
        self._actual_dose.update()
        self._refresh_effect_preview()

    def _refresh_effect_preview(self) -> None:
        fertilizer = self._selected_fertilizer()
        if fertilizer is None:
            self._target_effect_preview.text = "—"
            self._other_effects.text = self._t("fertilizer_effects_unavailable")
            return
        try:
            aquarium = self._current_aquarium()
            actual_dose_ml = self._actual_dose.value
            if actual_dose_ml is None:
                raise ValueError("Actual fertilizer dose must be a number.")
            predicted_effects = calculate_predicted_effects(
                gross_volume_liters=aquarium.volume_liters,
                dose_ml_per_100l=fertilizer.dose_ml_per_100l,
                actual_dose_ml=actual_dose_ml,
                effects={
                    effect.parameter_id: effect.ppm_per_dose
                    for effect in fertilizer.effects
                },
            )
            target_parameter_id = int(self._target_parameter.value)
        except (TypeError, ValueError, ValidationError, NotFoundError):
            self._target_effect_preview.text = "—"
            self._other_effects.text = self._t("fertilizer_effects_unavailable")
            return
        target_effect = predicted_effects.get(target_parameter_id)
        parameter_names = {
            effect.parameter_id: _format_parameter_name(effect.parameter.name)
            for effect in fertilizer.effects
        }
        target_parameter_name = parameter_names.get(target_parameter_id)
        self._target_effect_preview.text = (
            self._t(
                "fertilizer_effect_line",
                parameter=_format_parameter_name(target_parameter_name),
                ppm=target_effect,
            )
            if target_effect is not None and target_parameter_name is not None
            else "—"
        )
        remaining_effects = [
            self._t(
                "fertilizer_effect_line",
                parameter=parameter_names[parameter_id],
                ppm=ppm,
            )
            for parameter_id, ppm in predicted_effects.items()
            if parameter_id != target_parameter_id
        ]
        self._other_effects.text = (
            "; ".join(remaining_effects)
            if remaining_effects
            else self._t("no_other_fertilizer_effects")
        )

    def _t(self, key: str, **values: object) -> str:
        return translate(self._language, key, **values)
