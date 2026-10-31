from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from aqman.models import Parameter
from aqman.services import ParameterService, ValidationError
from aqman.translations import translate


class ParameterCatalog:
    def __init__(
        self,
        parameter_service: ParameterService,
        language: str,
        on_parameters_changed: Callable[[list[Parameter]], None],
        on_saved: Callable[[], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        self._parameter_service = parameter_service
        self._language = language
        self._on_parameters_changed = on_parameters_changed
        self._on_saved = on_saved
        self._on_error = on_error

        with ui.card().classes("w-full"):
            with ui.row().classes("items-center"):
                ui.label(self._t("parameter_definitions")).classes("text-h6")
                ui.button(
                    self._t("add_parameter"),
                    icon="add",
                    on_click=self.open_dialog,
                )
            ui.label(self._t("parameter_hint")).classes("text-body2")
            self._container = ui.column().classes("w-full")

    def refresh(self) -> None:
        parameters = self._parameter_service.list_parameters()
        self._on_parameters_changed(parameters)
        self._container.clear()
        with self._container:
            if not parameters:
                ui.label(self._t("empty_parameters"))
                return
            ui.table(
                columns=[
                    {
                        "name": "name",
                        "label": self._t("parameter"),
                        "field": "name",
                        "align": "left",
                    },
                    {
                        "name": "unit",
                        "label": self._t("table_unit"),
                        "field": "unit",
                        "align": "left",
                    },
                    {
                        "name": "description",
                        "label": self._t("description"),
                        "field": "description",
                        "align": "left",
                    },
                ],
                rows=[
                    {
                        "id": parameter.id,
                        "name": parameter.name,
                        "unit": parameter.unit,
                        "description": parameter.description or "",
                    }
                    for parameter in parameters
                ],
                row_key="id",
            ).classes("w-full")

    def open_dialog(self) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label(self._t("add_parameter_dialog")).classes("text-h6")
            name_input = ui.input(self._t("parameter_name_hint")).classes("w-full")
            unit_input = ui.input(self._t("unit_hint")).classes("w-full")
            description_input = ui.textarea(
                self._t("optional_description")
            ).classes("w-full")

            def save() -> None:
                try:
                    self._parameter_service.create_parameter(
                        name_input.value or "",
                        unit_input.value or "",
                        description_input.value,
                    )
                except ValidationError as error:
                    self._on_error(error)
                    return
                dialog.close()
                ui.notify(self._t("saved_parameter"), type="positive")
                self._on_saved()

            with ui.row().classes("justify-end"):
                ui.button(self._t("cancel"), on_click=dialog.close).props("flat")
                ui.button(self._t("save"), on_click=save, icon="save")
        dialog.open()

    def _t(self, key: str) -> str:
        return translate(self._language, key)
