from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from nicegui import ui

from aqman.models import WaterSource
from aqman.services import ValidationError
from aqman.translations import translate
from aqman.ui.components.date_time_picker import DateTimePicker


@dataclass(frozen=True)
class WaterChangeValues:
    timestamp: datetime
    source: WaterSource
    volume_liters: float
    description: str | None


class WaterChangeForm:
    def __init__(
        self,
        language: str,
        source_options: dict[str, str],
        on_save: Callable[[WaterChangeForm], None],
        show_time: bool = True,
    ) -> None:
        self._language = language
        self._on_save = on_save

        with ui.card().classes("w-full"):
            ui.label(self._t("new_water_change")).classes("text-h6")
            self._datetime = DateTimePicker(
                self._t("date_time"),
                show_time=show_time,
            )
            self._source = ui.select(
                source_options,
                label=self._t("water_source"),
                value=WaterSource.RO.value,
            ).classes("w-full")
            self._volume = ui.number(
                self._t("water_volume"),
                min=0,
            ).classes("w-full")
            self._description = ui.textarea(
                self._t("optional_description")
            ).classes("w-full")
            ui.button(
                self._t("save_water_change"),
                icon="save",
                on_click=lambda: self._on_save(self),
            )

    @property
    def values(self) -> WaterChangeValues:
        try:
            source = WaterSource(self._source.value)
        except (TypeError, ValueError) as error:
            raise ValidationError("Select a valid water source.") from error
        try:
            volume_liters = float(self._volume.value)
        except (TypeError, ValueError) as error:
            raise ValidationError("Water-change volume must be a number.") from error
        return WaterChangeValues(
            timestamp=self._datetime.value,
            source=source,
            volume_liters=volume_liters,
            description=self._description.value,
        )

    def reset_after_save(self) -> None:
        self._volume.value = None
        self._description.value = ""
        self._datetime.set_value(datetime.now().astimezone())

    def _t(self, key: str) -> str:
        return translate(self._language, key)
