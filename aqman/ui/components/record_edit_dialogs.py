from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from aqman.models import WaterSource
from aqman.services import (
    FertilizerService,
    NotFoundError,
    ParameterService,
    RecordService,
    ValidationError,
)
from aqman.translations import translate
from aqman.ui.components.date_time_picker import DateTimePicker


class RecordEditDialogs:
    def __init__(
        self,
        record_service: RecordService,
        parameter_service: ParameterService,
        fertilizer_service: FertilizerService,
        aquarium_id_provider: Callable[[], int],
        language: str,
        source_options: dict[str, str],
        on_saved: Callable[[], None],
        on_error: Callable[[Exception], None],
        show_time: bool = True,
    ) -> None:
        self._record_service = record_service
        self._parameter_service = parameter_service
        self._fertilizer_service = fertilizer_service
        self._aquarium_id_provider = aquarium_id_provider
        self._language = language
        self._source_options = source_options
        self._on_saved = on_saved
        self._on_error = on_error
        self._show_time = show_time

    def open_note(self, note_id: int) -> None:
        try:
            aquarium_id = self._aquarium_id_provider()
            note = self._record_service.get_note(aquarium_id, note_id)
        except (ValidationError, NotFoundError) as error:
            self._on_error(error)
            return

        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label(self._t("edit_note_dialog")).classes("text-h6")
            note_datetime = DateTimePicker(
                self._t("date_time"),
                note.timestamp,
                show_time=self._show_time,
            )
            category_input = ui.input(
                self._t("optional_category"),
                value=note.category or "",
            ).classes("w-full")
            content_input = ui.textarea(
                self._t("note_content"),
                value=note.content,
            ).classes("w-full")

            def save() -> None:
                try:
                    self._record_service.update_note(
                        aquarium_id,
                        note.id,
                        note_datetime.value,
                        category_input.value,
                        content_input.value or "",
                    )
                except (ValidationError, NotFoundError) as error:
                    self._on_error(error)
                    return
                dialog.close()
                ui.notify(self._t("updated_note"), type="positive")
                self._on_saved()

            with ui.row().classes("justify-end"):
                ui.button(self._t("cancel"), on_click=dialog.close).props("flat")
                ui.button(self._t("save"), on_click=save, icon="save")
        dialog.open()

    def open_measurement(self, measurement_id: int) -> None:
        try:
            aquarium_id = self._aquarium_id_provider()
            measurement = self._record_service.get_measurement(
                aquarium_id,
                measurement_id,
            )
        except (ValidationError, NotFoundError) as error:
            self._on_error(error)
            return

        parameter_options = {
            parameter.id: f"{parameter.name} ({parameter.unit})"
            for parameter in self._parameter_service.list_parameters()
        }
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label(self._t("edit_measurement_dialog")).classes("text-h6")
            measurement_datetime = DateTimePicker(
                self._t("date_time"),
                measurement.timestamp,
                show_time=self._show_time,
            )
            parameter_input = ui.select(
                parameter_options,
                label=self._t("parameter"),
                value=measurement.parameter_id,
            ).classes("w-full")
            value_input = ui.number(
                self._t("value"),
                value=measurement.value,
            ).classes("w-full")
            note_input = ui.input(
                self._t("optional_note"),
                value=measurement.note or "",
            ).classes("w-full")

            def save() -> None:
                try:
                    try:
                        parameter_id = int(parameter_input.value)
                    except (TypeError, ValueError) as error:
                        raise ValidationError("Select a parameter first.") from error
                    self._record_service.update_measurement(
                        aquarium_id,
                        measurement.id,
                        measurement_datetime.value,
                        parameter_id,
                        value_input.value,
                        note_input.value,
                    )
                except (ValidationError, NotFoundError) as error:
                    self._on_error(error)
                    return
                dialog.close()
                ui.notify(self._t("updated_measurement"), type="positive")
                self._on_saved()

            def confirm_delete() -> None:
                with ui.dialog() as confirmation, ui.card().classes("w-full max-w-md"):
                    ui.label(self._t("confirm_delete_measurement"))

                    def delete() -> None:
                        try:
                            self._record_service.delete_measurement(
                                aquarium_id,
                                measurement.id,
                            )
                        except (ValidationError, NotFoundError) as error:
                            self._on_error(error)
                            confirmation.close()
                            return
                        confirmation.close()
                        dialog.close()
                        ui.notify(
                            self._t("deleted_measurement"),
                            type="positive",
                        )
                        self._on_saved()

                    with ui.row().classes("justify-end"):
                        ui.button(
                            self._t("cancel"),
                            on_click=confirmation.close,
                        ).props("flat")
                        ui.button(
                            self._t("delete_measurement"),
                            icon="delete",
                            on_click=delete,
                        ).props("color=negative")
                confirmation.open()

            with ui.row().classes("justify-end"):
                ui.button(self._t("cancel"), on_click=dialog.close).props("flat")
                ui.button(self._t("save"), on_click=save, icon="save")
                ui.button(
                    self._t("delete_measurement"),
                    icon="delete",
                    on_click=confirm_delete,
                ).props("color=negative")
        dialog.open()

    def open_fertilizer_application(self, application_id: int) -> None:
        try:
            aquarium_id = self._aquarium_id_provider()
            application = self._record_service.get_fertilizer_application(
                aquarium_id,
                application_id,
            )
        except (ValidationError, NotFoundError) as error:
            self._on_error(error)
            return

        fertilizers = self._fertilizer_service.list_fertilizers()
        fertilizer_options = {
            fertilizer.id: fertilizer.name for fertilizer in fertilizers
        }
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label(self._t("edit_fertilizer_application")).classes("text-h6")
            application_datetime = DateTimePicker(
                self._t("date_time"),
                application.timestamp,
                show_time=self._show_time,
            )
            fertilizer_input = ui.select(
                fertilizer_options,
                label=self._t("fertilizer"),
                value=application.fertilizer_id,
            ).classes("w-full")
            dose_input = ui.number(
                self._t("fertilizer_actual_dose"),
                value=application.actual_dose_ml,
                min=0,
            ).classes("w-full")
            notes_input = ui.textarea(
                self._t("optional_note"),
                value=application.notes or "",
            ).classes("w-full")

            def save() -> None:
                try:
                    try:
                        fertilizer_id = int(fertilizer_input.value)
                    except (TypeError, ValueError) as error:
                        raise ValidationError("Select a fertilizer first.") from error
                    self._record_service.update_fertilizer_application(
                        aquarium_id,
                        application.id,
                        application_datetime.value,
                        fertilizer_id,
                        dose_input.value,
                        notes_input.value,
                    )
                except (ValidationError, NotFoundError) as error:
                    self._on_error(error)
                    return
                dialog.close()
                ui.notify(self._t("updated_fertilizer_application"), type="positive")
                self._on_saved()

            def confirm_delete() -> None:
                with ui.dialog() as confirmation, ui.card().classes("w-full max-w-md"):
                    ui.label(self._t("confirm_delete_fertilizer_application"))

                    def delete() -> None:
                        try:
                            self._record_service.delete_fertilizer_application(
                                aquarium_id,
                                application.id,
                            )
                        except (ValidationError, NotFoundError) as error:
                            self._on_error(error)
                            confirmation.close()
                            return
                        confirmation.close()
                        dialog.close()
                        ui.notify(
                            self._t("deleted_fertilizer_application"),
                            type="positive",
                        )
                        self._on_saved()

                    with ui.row().classes("justify-end"):
                        ui.button(
                            self._t("cancel"),
                            on_click=confirmation.close,
                        ).props("flat")
                        ui.button(
                            self._t("delete_fertilizer_application"),
                            icon="delete",
                            on_click=delete,
                        ).props("color=negative")
                confirmation.open()

            with ui.row().classes("w-full justify-between"):
                ui.button(
                    self._t("delete_fertilizer_application"),
                    icon="delete",
                    on_click=confirm_delete,
                ).props("color=negative flat")
                with ui.row().classes("justify-end"):
                    ui.button(
                        self._t("cancel"),
                        on_click=dialog.close,
                    ).props("flat")
                    ui.button(self._t("save"), on_click=save, icon="save")
        dialog.open()

    def open_water_change(self, water_change_id: int) -> None:
        try:
            aquarium_id = self._aquarium_id_provider()
            water_change = self._record_service.get_water_change(
                aquarium_id,
                water_change_id,
            )
        except (ValidationError, NotFoundError) as error:
            self._on_error(error)
            return

        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label(self._t("edit_water_change_dialog")).classes("text-h6")
            water_change_datetime = DateTimePicker(
                self._t("date_time"),
                water_change.timestamp,
                show_time=self._show_time,
            )
            source_input = ui.select(
                self._source_options,
                label=self._t("water_source"),
                value=water_change.source.value,
            ).classes("w-full")
            volume_input = ui.number(
                self._t("water_volume"),
                value=water_change.volume_liters,
                min=0,
            ).classes("w-full")
            description_input = ui.textarea(
                self._t("optional_description"),
                value=water_change.description or "",
            ).classes("w-full")

            def save() -> None:
                try:
                    try:
                        source = WaterSource(source_input.value)
                    except (TypeError, ValueError) as error:
                        raise ValidationError("Select a valid water source.") from error
                    self._record_service.update_water_change(
                        aquarium_id,
                        water_change.id,
                        water_change_datetime.value,
                        source,
                        volume_input.value,
                        description_input.value,
                    )
                except (ValidationError, NotFoundError) as error:
                    self._on_error(error)
                    return
                dialog.close()
                ui.notify(self._t("updated_water_change"), type="positive")
                self._on_saved()

            with ui.row().classes("justify-end"):
                ui.button(self._t("cancel"), on_click=dialog.close).props("flat")
                ui.button(self._t("save"), on_click=save, icon="save")
        dialog.open()

    def _t(self, key: str) -> str:
        return translate(self._language, key)
