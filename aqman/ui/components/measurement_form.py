from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from nicegui import ui

from aqman.models import Parameter
from aqman.services import ValidationError
from aqman.translations import translate
from aqman.ui.components.date_time_picker import DateTimePicker


@dataclass(frozen=True)
class MeasurementValues:
    timestamp: datetime
    parameter_id: int
    value: float
    note: str | None


class MeasurementForm:
    def __init__(
        self,
        language: str,
        on_save: Callable[[MeasurementForm], None],
    ) -> None:
        self._language = language
        self._on_save = on_save

        with ui.card().classes("w-full"):
            ui.label(self._t("add_measurement")).classes("text-h6")
            self._datetime = DateTimePicker(self._t("date_time"))
            self._parameter = ui.select(
                {},
                label=self._t("parameter"),
            ).classes("w-full")
            self._value = ui.number(self._t("value")).classes("w-full")
            self._note = ui.input(self._t("optional_note")).classes("w-full")
            ui.button(
                self._t("save_measurement"),
                icon="save",
                on_click=lambda: self._on_save(self),
            )

    @property
    def values(self) -> MeasurementValues:
        try:
            parameter_id = int(self._parameter.value)
        except (TypeError, ValueError) as error:
            raise ValidationError("Select a parameter first.") from error
        try:
            value = float(self._value.value)
        except (TypeError, ValueError) as error:
            raise ValidationError("Measurement value must be a number.") from error
        return MeasurementValues(
            timestamp=self._datetime.value,
            parameter_id=parameter_id,
            value=value,
            note=self._note.value,
        )

    def set_parameters(self, parameters: list[Parameter]) -> None:
        options = {
            parameter.id: f"{parameter.name} ({parameter.unit})"
            for parameter in parameters
        }
        try:
            previous_parameter_id = int(self._parameter.value)
        except (TypeError, ValueError):
            previous_parameter_id = None
        self._parameter.options = options
        self._parameter.value = (
            previous_parameter_id
            if previous_parameter_id in options
            else next(iter(options), None)
        )
        self._parameter.update()

    def reset_after_save(self) -> None:
        self._value.value = None
        self._note.value = ""
        self._datetime.set_value(datetime.now().astimezone())

    def _t(self, key: str) -> str:
        return translate(self._language, key)
