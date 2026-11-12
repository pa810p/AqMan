from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from aqman.models import Parameter
from aqman.services import (
    NotFoundError,
    ParameterService,
    ValidationError,
)
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
            for parameter in parameters:
                with ui.row().classes("w-full items-start justify-between"):
                    with ui.column().classes("gap-1"):
                        ui.label(parameter.name).classes("text-subtitle1")
                        ui.label(parameter.unit).classes("text-body2")
                        if parameter.description:
                            ui.label(parameter.description).classes("text-body2")
                    ui.button(
                        icon="edit",
                        on_click=lambda item=parameter: self.open_dialog(item),
                    ).props("flat round").tooltip(self._t("edit_parameter"))
                    ui.button(
                        icon="delete",
                        on_click=lambda parameter_id=parameter.id: self.confirm_delete(
                            parameter_id
                        ),
                    ).props("flat round").tooltip(self._t("delete_parameter"))
                ui.separator()

    def open_dialog(self, parameter: Parameter | None = None) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label(
                self._t(
                    "edit_parameter_dialog"
                    if parameter is not None
                    else "add_parameter_dialog"
                )
            ).classes("text-h6")
            name_input = ui.input(
                self._t("parameter_name_hint"),
                value=parameter.name if parameter is not None else "",
            ).classes("w-full")
            unit_input = ui.input(
                self._t("unit_hint"),
                value=parameter.unit if parameter is not None else "",
            ).classes("w-full")
            description_input = ui.textarea(
                self._t("optional_description"),
                value=parameter.description or "" if parameter is not None else "",
            ).classes("w-full")
            chart_min_input = ui.number(
                self._t("parameter_scale_min"),
                value=(
                    parameter.chart_min_value
                    if parameter is not None
                    else None
                ),
                step=0.1,
            ).classes("w-full")
            chart_max_input = ui.number(
                self._t("parameter_scale_max"),
                value=(
                    parameter.chart_max_value
                    if parameter is not None
                    else None
                ),
                step=0.1,
            ).classes("w-full")
            ui.label(self._t("parameter_scale_hint")).classes("text-body2")

            def save() -> None:
                try:
                    if parameter is None:
                        self._parameter_service.create_parameter(
                            name_input.value or "",
                            unit_input.value or "",
                            description_input.value,
                            chart_min_input.value,
                            chart_max_input.value,
                        )
                        notification_key = "saved_parameter"
                    else:
                        self._parameter_service.update_parameter(
                            parameter.id,
                            name_input.value or "",
                            unit_input.value or "",
                            description_input.value,
                            chart_min_input.value,
                            chart_max_input.value,
                        )
                        notification_key = "updated_parameter"
                except (NotFoundError, ValidationError) as error:
                    self._on_error(error)
                    return
                dialog.close()
                ui.notify(self._t(notification_key), type="positive")
                self._on_saved()

            with ui.row().classes("justify-end"):
                ui.button(self._t("cancel"), on_click=dialog.close).props("flat")
                ui.button(self._t("save"), on_click=save, icon="save")
        dialog.open()

    def confirm_delete(self, parameter_id: int) -> None:
        with ui.dialog() as confirmation, ui.card().classes("w-full max-w-md"):
            ui.label(self._t("confirm_delete_parameter"))

            def delete() -> None:
                try:
                    self._parameter_service.delete_parameter(parameter_id)
                except (NotFoundError, ValidationError) as error:
                    confirmation.close()
                    self._on_error(error)
                    return
                confirmation.close()
                ui.notify(self._t("deleted_parameter"), type="positive")
                self._on_saved()

            with ui.row().classes("justify-end"):
                ui.button(
                    self._t("cancel"),
                    on_click=confirmation.close,
                ).props("flat")
                ui.button(
                    self._t("delete_parameter"),
                    icon="delete",
                    on_click=delete,
                ).props("color=negative")
        confirmation.open()

    def _t(self, key: str) -> str:
        return translate(self._language, key)
