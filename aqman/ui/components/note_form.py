from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from nicegui import ui

from aqman.translations import translate
from aqman.ui.components.date_time_picker import DateTimePicker


@dataclass(frozen=True)
class NoteValues:
    timestamp: datetime
    category: str | None
    content: str


class NoteForm:
    def __init__(
        self,
        language: str,
        on_save: Callable[[NoteForm], None],
    ) -> None:
        self._language = language
        self._on_save = on_save

        with ui.card().classes("w-full"):
            ui.label(self._t("new_note")).classes("text-h6")
            self._datetime = DateTimePicker(self._t("date_time"))
            self._category = ui.input(
                self._t("optional_category")
            ).classes("w-full")
            self._content = ui.textarea(self._t("note_content")).classes("w-full")
            ui.button(
                self._t("save_note"),
                icon="save",
                on_click=lambda: self._on_save(self),
            )

    @property
    def values(self) -> NoteValues:
        return NoteValues(
            timestamp=self._datetime.value,
            category=self._category.value,
            content=self._content.value or "",
        )

    def reset_after_save(self) -> None:
        self._category.value = ""
        self._content.value = ""
        self._datetime.set_value(datetime.now().astimezone())

    def _t(self, key: str) -> str:
        return translate(self._language, key)
