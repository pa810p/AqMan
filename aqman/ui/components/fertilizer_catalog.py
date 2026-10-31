from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from aqman.models import Fertilizer
from aqman.services import (
    FertilizerService,
    NotFoundError,
    ValidationError,
)
from aqman.translations import translate


class FertilizerCatalog:
    def __init__(
        self,
        fertilizer_service: FertilizerService,
        language: str,
        on_fertilizers_changed: Callable[[list[Fertilizer]], None],
        on_saved: Callable[[], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        self._fertilizer_service = fertilizer_service
        self._language = language
        self._on_fertilizers_changed = on_fertilizers_changed
        self._on_saved = on_saved
        self._on_error = on_error

        with ui.card().classes("w-full"):
            with ui.row().classes("items-center"):
                ui.label(self._t("fertilizer_catalog")).classes("text-h6")
                ui.button(
                    self._t("add_fertilizer"),
                    icon="add",
                    on_click=lambda: self.open_dialog(),
                )
            self._container = ui.column().classes("w-full")

    def refresh(self) -> None:
        fertilizers = self._fertilizer_service.list_fertilizers()
        self._on_fertilizers_changed(fertilizers)
        self._container.clear()
        with self._container:
            if not fertilizers:
                ui.label(self._t("empty_fertilizers"))
                return
            for fertilizer in fertilizers:
                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-start justify-between"):
                        with ui.column().classes("gap-1"):
                            ui.label(fertilizer.name).classes("text-subtitle1")
                            ui.label(
                                self._t(
                                    "fertilizer_dose_summary",
                                    dose=fertilizer.dose_ml_per_100l,
                                )
                            ).classes("text-body2")
                        with ui.row().classes("items-center"):
                            ui.button(
                                self._t("edit_fertilizer"),
                                icon="edit",
                                on_click=lambda fertilizer_id=fertilizer.id: self.open_dialog(
                                    fertilizer_id
                                ),
                            ).props("flat")
                            ui.button(
                                self._t("delete_fertilizer"),
                                icon="delete",
                                on_click=lambda fertilizer_id=fertilizer.id, name=fertilizer.name: self.confirm_delete(
                                    fertilizer_id,
                                    name,
                                ),
                            ).props("flat")
                    ui.separator()
                    with ui.column().classes("w-full gap-1"):
                        for effect in fertilizer.effects:
                            ui.label(
                                self._t(
                                    "fertilizer_effect_line",
                                    parameter=(
                                        f"{effect.parameter.name} "
                                        f"({effect.parameter.unit})"
                                    ),
                                    ppm=effect.ppm_per_dose,
                                )
                            )

    def open_dialog(self, fertilizer_id: int | None = None) -> None:
        fertilizer: Fertilizer | None = None
        if fertilizer_id is not None:
            try:
                fertilizer = self._fertilizer_service.get_fertilizer(fertilizer_id)
            except NotFoundError as error:
                self._on_error(error)
                return

        parameters = self._fertilizer_service.list_effect_parameters()
        parameter_by_id = {parameter.id: parameter for parameter in parameters}
        parameter_options = {
            parameter.id: f"{parameter.name} ({parameter.unit})"
            for parameter in parameters
        }

        with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl"):
            ui.label(
                self._t("edit_fertilizer_dialog")
                if fertilizer
                else self._t("add_fertilizer_dialog")
            ).classes("text-h6")
            name_input = ui.input(
                self._t("fertilizer_name"),
                value=fertilizer.name if fertilizer else "",
            ).classes("w-full")
            dose_input = ui.number(
                self._t("fertilizer_dose"),
                value=fertilizer.dose_ml_per_100l if fertilizer else None,
                min=0,
            ).classes("w-full")
            ui.label(self._t("fertilizer_effects")).classes("text-subtitle1")
            if not parameters:
                ui.label(self._t("no_fertilizer_parameters")).classes("text-body2")
            effect_rows_container = ui.column().classes("w-full")
            effect_rows = []

            def parameter_id_for(value: object) -> int | None:
                try:
                    return int(value) if value is not None else None
                except (TypeError, ValueError):
                    return None

            def update_effect_options() -> None:
                for _, parameter_input, _, _ in effect_rows:
                    selected_parameter_id = parameter_id_for(parameter_input.value)
                    used_compounds = {
                        parameter_by_id[other_id].name.strip().casefold()
                        for _, other_input, _, _ in effect_rows
                        if other_input is not parameter_input
                        if (other_id := parameter_id_for(other_input.value))
                        in parameter_by_id
                    }
                    current_compound = (
                        parameter_by_id[selected_parameter_id].name.strip().casefold()
                        if selected_parameter_id in parameter_by_id
                        else None
                    )
                    available_options = {
                        parameter.id: f"{parameter.name} ({parameter.unit})"
                        for parameter in parameters
                        if parameter.name.strip().casefold() not in used_compounds
                        or parameter.name.strip().casefold() == current_compound
                    }
                    parameter_input.options = available_options
                    parameter_input.update()

            def handle_parameter_change(changed_input) -> None:
                changed_parameter_id = parameter_id_for(changed_input.value)
                if changed_parameter_id in parameter_by_id:
                    changed_compound = (
                        parameter_by_id[changed_parameter_id].name.strip().casefold()
                    )
                    for _, other_input, _, _ in effect_rows:
                        if other_input is changed_input:
                            continue
                        other_id = parameter_id_for(other_input.value)
                        if (
                            other_id in parameter_by_id
                            and parameter_by_id[other_id].name.strip().casefold()
                            == changed_compound
                        ):
                            other_input.value = None
                            other_input.update()
                update_effect_options()

            def update_remove_buttons() -> None:
                for _, _, _, remove_button in effect_rows:
                    if len(effect_rows) == 1:
                        remove_button.disable()
                    else:
                        remove_button.enable()

            def remove_effect_row(row_to_remove) -> None:
                if len(effect_rows) <= 1:
                    return
                row_to_remove.delete()
                effect_rows[:] = [
                    row for row in effect_rows if row[0] is not row_to_remove
                ]
                update_effect_options()
                update_remove_buttons()

            def add_effect_row(
                parameter_id: int | None = None,
                ppm_per_dose: float | None = None,
            ) -> None:
                with effect_rows_container:
                    with ui.row().classes("w-full items-center gap-2") as row:
                        parameter_input = ui.select(
                            parameter_options,
                            label=self._t("fertilizer_effect_parameter"),
                            value=parameter_id,
                        ).classes("min-w-0 flex-1")
                        ppm_input = ui.number(
                            self._t("fertilizer_effect_ppm"),
                            value=ppm_per_dose,
                            min=0,
                        ).classes("min-w-0 flex-1")
                        remove_button = ui.button(
                            icon="close",
                            on_click=lambda: remove_effect_row(row),
                        ).props("flat round").tooltip(
                            self._t("remove_fertilizer_effect")
                        )
                effect_rows.append((row, parameter_input, ppm_input, remove_button))
                parameter_input.on_value_change(
                    lambda _: handle_parameter_change(parameter_input)
                )
                update_effect_options()
                update_remove_buttons()

            if fertilizer:
                for effect in fertilizer.effects:
                    add_effect_row(effect.parameter_id, effect.ppm_per_dose)
            else:
                add_effect_row()

            ui.button(
                self._t("add_fertilizer_effect"),
                icon="add",
                on_click=lambda: add_effect_row(),
            ).props("flat")

            def save() -> None:
                try:
                    if dose_input.value is None:
                        raise ValidationError("Base dose must be a number.")
                    dose = float(dose_input.value)
                    effects: list[tuple[int, float]] = []
                    for _, parameter_input, ppm_input, _ in effect_rows:
                        parameter_id = parameter_id_for(parameter_input.value)
                        if parameter_id is None:
                            raise ValidationError(
                                "Select a water parameter for every fertilizer effect."
                            )
                        if ppm_input.value is None:
                            raise ValidationError("Fertilizer effect must be a number.")
                        effects.append((parameter_id, float(ppm_input.value)))
                    if fertilizer:
                        self._fertilizer_service.update_fertilizer(
                            fertilizer.id,
                            name_input.value or "",
                            dose,
                            effects,
                        )
                    else:
                        self._fertilizer_service.create_fertilizer(
                            name_input.value or "",
                            dose,
                            effects,
                        )
                except (
                    NotFoundError,
                    ValidationError,
                    TypeError,
                    ValueError,
                ) as error:
                    if isinstance(error, (TypeError, ValueError)) and not isinstance(
                        error,
                        ValidationError,
                    ):
                        error = ValidationError("Enter valid fertilizer values.")
                    self._on_error(error)
                    return
                dialog.close()
                ui.notify(self._t("saved_fertilizer"), type="positive")
                self._on_saved()

            with ui.row().classes("justify-end"):
                ui.button(self._t("cancel"), on_click=dialog.close).props("flat")
                ui.button(self._t("save"), on_click=save, icon="save")
        dialog.open()

    def confirm_delete(self, fertilizer_id: int, name: str) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-md"):
            ui.label(self._t("confirm_delete_fertilizer", name=name))

            def delete() -> None:
                try:
                    self._fertilizer_service.delete_fertilizer(fertilizer_id)
                except (NotFoundError, ValidationError) as error:
                    self._on_error(error)
                    dialog.close()
                    self.refresh()
                    return
                dialog.close()
                ui.notify(self._t("deleted_fertilizer"), type="positive")
                self._on_saved()

            with ui.row().classes("justify-end"):
                ui.button(self._t("cancel"), on_click=dialog.close).props("flat")
                ui.button(
                    self._t("delete_fertilizer"),
                    icon="delete",
                    on_click=delete,
                ).props("color=negative")
        dialog.open()

    def _t(self, key: str, **values: object) -> str:
        return translate(self._language, key, **values)
