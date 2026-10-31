from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from aqman.models import FertilizerApplication, WaterChange, WaterSource
from aqman.services import (
    DailyAquariumHistory,
    NotFoundError,
    RecordService,
    ValidationError,
)
from aqman.translations import translate
from aqman.ui.components.record_edit_dialogs import RecordEditDialogs


class ActivityHistory:
    def __init__(
        self,
        record_service: RecordService,
        aquarium_id_provider: Callable[[], int],
        language: str,
        water_source_labels: dict[WaterSource, str],
        edit_dialogs_provider: Callable[[], RecordEditDialogs],
        on_error: Callable[[Exception], None],
    ) -> None:
        self._record_service = record_service
        self._aquarium_id_provider = aquarium_id_provider
        self._language = language
        self._water_source_labels = water_source_labels
        self._edit_dialogs_provider = edit_dialogs_provider
        self._on_error = on_error

        with ui.card().classes("w-full col-span-2"):
            ui.label(self._t("activity_history")).classes("text-h6")
            self._container = ui.column().classes("w-full")

    def refresh(self) -> None:
        self._container.clear()
        with self._container:
            try:
                aquarium_id = self._aquarium_id_provider()
            except ValidationError:
                ui.label(self._t("empty_history"))
                return

            daily_history = self._record_service.daily_history(aquarium_id)
            if not daily_history:
                ui.label(self._t("empty_history"))
                return

            parameter_details = {
                parameter_id: (
                    measurements[0].parameter.name,
                    measurements[0].parameter.unit,
                )
                for day in daily_history
                for parameter_id, measurements in day.measurements.items()
            }
            parameter_ids = sorted(
                parameter_details,
                key=lambda parameter_id: (
                    parameter_details[parameter_id][0].casefold(),
                    parameter_details[parameter_id][1].casefold(),
                ),
            )
            columns = [
                {
                    "name": "date",
                    "label": self._t("history_date"),
                    "field": "date",
                    "align": "left",
                },
                *[
                    {
                        "name": f"parameter_{parameter_id}",
                        "label": (
                            f"{parameter_details[parameter_id][0]} "
                            f"({parameter_details[parameter_id][1]})"
                        ),
                        "field": f"parameter_{parameter_id}",
                        "align": "right",
                    }
                    for parameter_id in parameter_ids
                ],
                {
                    "name": "fertilizer_applications",
                    "label": self._t("history_fertilizer_applications"),
                    "field": "fertilizer_applications",
                    "align": "left",
                },
                {
                    "name": "water_changes",
                    "label": self._t("history_water_changes"),
                    "field": "water_changes",
                    "align": "left",
                },
                {
                    "name": "notes",
                    "label": self._t("history_notes"),
                    "field": "notes",
                    "align": "left",
                },
            ]
            rows = [
                self._history_row(day, parameter_ids)
                for day in daily_history
            ]
            history_table = ui.table(
                columns=columns,
                rows=rows,
                row_key="id",
            ).classes("w-full")
            self._add_measurement_slots(history_table, parameter_ids)
            self._add_record_slots(history_table)
            self._connect_edit_handlers(history_table)

    def _history_row(
        self,
        day: DailyAquariumHistory,
        parameter_ids: list[int],
    ) -> dict[str, object]:
        note_links = [
            {
                "id": f"note-{note.id}",
                "preview": self._note_preview(note.content),
                "content": note.content,
            }
            for note in day.notes
        ]
        note_links.extend(
            {
                "id": f"measurement-{measurement.id}",
                "preview": self._note_preview(measurement.note),
                "content": measurement.note,
            }
            for measurements in day.measurements.values()
            for measurement in measurements
            if measurement.note
        )
        note_links.extend(
            {
                "id": f"fertilizer-application-{application.id}",
                "preview": self._note_preview(application.notes),
                "content": application.notes,
            }
            for application in day.fertilizer_applications
            if application.notes
        )
        row: dict[str, object] = {
            "id": day.day.isoformat(),
            "date": day.day.isoformat(),
            "water_changes": [
                {
                    "id": water_change.id,
                    "label": self._format_water_change(water_change),
                }
                for water_change in day.water_changes
            ],
            "fertilizer_applications": [
                {
                    "id": application.id,
                    "label": self._format_fertilizer_application(application),
                }
                for application in day.fertilizer_applications
            ],
            "notes": note_links,
        }
        for parameter_id in parameter_ids:
            row[f"parameter_{parameter_id}"] = [
                {
                    "id": measurement.id,
                    "value": f"{measurement.value:g}",
                }
                for measurement in day.measurements.get(parameter_id, ())
            ]
        return row

    def _format_water_change(self, water_change: WaterChange) -> str:
        entry = self._t(
            "history_water_change_entry",
            source=self._water_source_labels[water_change.source],
            volume=water_change.volume_liters,
        )
        if water_change.description:
            return f"{entry} ({water_change.description})"
        return entry

    def _format_fertilizer_application(
        self,
        application: FertilizerApplication,
    ) -> str:
        return self._t(
            "history_fertilizer_application_entry",
            name=application.fertilizer.name,
            dose=application.actual_dose_ml,
        )

    def _add_measurement_slots(self, history_table, parameter_ids: list[int]) -> None:
        for parameter_id in parameter_ids:
            column_name = f"parameter_{parameter_id}"
            measurement_slot = """
            <q-td :props="props">
                <span
                    v-for="(measurement, index) in props.row.__COLUMN__"
                    :key="measurement.id"
                >
                    <a
                        href="#"
                        class="text-primary underline cursor-pointer"
                        @click.prevent="$parent.$emit('measurement-edit-click', measurement.id)"
                    >
                        {{ measurement.value }}
                        <q-tooltip>__EDIT_LABEL__</q-tooltip>
                    </a>
                    <span v-if="index + 1 < props.row.__COLUMN__.length">, </span>
                </span>
            </q-td>
            """
            history_table.add_slot(
                f"body-cell-{column_name}",
                measurement_slot.replace("__COLUMN__", column_name).replace(
                    "__EDIT_LABEL__", self._t("edit_measurement")
                ),
            )

    def _add_record_slots(self, history_table) -> None:
        history_table.add_slot(
            "body-cell-fertilizer_applications",
            """
            <q-td :props="props">
                <span
                    v-for="(application, index) in props.row.fertilizer_applications"
                    :key="application.id"
                >
                    <a
                        href="#"
                        class="text-primary underline cursor-pointer"
                        @click.prevent="$parent.$emit('fertilizer-application-edit-click', application.id)"
                    >
                        {{ application.label }}
                        <q-tooltip>__EDIT_LABEL__</q-tooltip>
                    </a>
                    <span v-if="index + 1 < props.row.fertilizer_applications.length">; </span>
                </span>
            </q-td>
            """.replace("__EDIT_LABEL__", self._t("edit_fertilizer_application")),
        )
        history_table.add_slot(
            "body-cell-water_changes",
            """
            <q-td :props="props">
                <span
                    v-for="(waterChange, index) in props.row.water_changes"
                    :key="waterChange.id"
                >
                    <a
                        href="#"
                        class="text-primary underline cursor-pointer"
                        @click.prevent="$parent.$emit('water-change-edit-click', waterChange.id)"
                    >
                        {{ waterChange.label }}
                        <q-tooltip>__EDIT_LABEL__</q-tooltip>
                    </a>
                    <span v-if="index + 1 < props.row.water_changes.length">; </span>
                </span>
            </q-td>
            """.replace("__EDIT_LABEL__", self._t("edit_water_change")),
        )
        history_table.add_slot(
            "body-cell-notes",
            """
            <q-td :props="props">
                <span v-for="(note, index) in props.row.notes" :key="note.id">
                    <a
                        href="#"
                        class="text-primary underline cursor-pointer"
                        @click.prevent="$parent.$emit('note-edit-click', note.id)"
                    >
                        {{ note.preview }}
                        <q-tooltip max-width="400px">
                            <div style="white-space: pre-wrap">{{ note.content }}</div>
                        </q-tooltip>
                    </a>
                    <span v-if="index + 1 < props.row.notes.length"> · </span>
                </span>
            </q-td>
            """,
        )

    def _connect_edit_handlers(self, history_table) -> None:
        history_table.on("note-edit-click", self._handle_note_edit)
        history_table.on(
            "measurement-edit-click",
            self._handle_measurement_edit,
        )
        history_table.on(
            "water-change-edit-click",
            self._handle_water_change_edit,
        )
        history_table.on(
            "fertilizer-application-edit-click",
            self._handle_fertilizer_application_edit,
        )

    def _handle_note_edit(self, event) -> None:
        note_type, separator, identifier = str(event.args).rpartition("-")
        if not separator:
            self._on_error(NotFoundError("Note not found."))
            return
        try:
            record_id = int(identifier)
        except ValueError:
            self._on_error(NotFoundError("Note not found."))
            return
        edit_dialogs = self._edit_dialogs_provider()
        if note_type == "note":
            edit_dialogs.open_note(record_id)
        elif note_type == "measurement":
            edit_dialogs.open_measurement(record_id)
        elif note_type == "fertilizer-application":
            edit_dialogs.open_fertilizer_application(record_id)
        else:
            self._on_error(NotFoundError("Note not found."))

    def _handle_measurement_edit(self, event) -> None:
        try:
            measurement_id = int(event.args)
        except (TypeError, ValueError):
            self._on_error(NotFoundError("Measurement not found."))
            return
        self._edit_dialogs_provider().open_measurement(measurement_id)

    def _handle_water_change_edit(self, event) -> None:
        try:
            water_change_id = int(event.args)
        except (TypeError, ValueError):
            self._on_error(NotFoundError("Water change not found."))
            return
        self._edit_dialogs_provider().open_water_change(water_change_id)

    def _handle_fertilizer_application_edit(self, event) -> None:
        try:
            application_id = int(event.args)
        except (TypeError, ValueError):
            self._on_error(NotFoundError("Fertilizer application not found."))
            return
        self._edit_dialogs_provider().open_fertilizer_application(application_id)

    def _note_preview(self, content: str) -> str:
        words = content.split()
        if len(words) <= 6:
            return " ".join(words)
        return f"{' '.join(words[:6])}…"

    def _t(self, key: str, **values: object) -> str:
        return translate(self._language, key, **values)
