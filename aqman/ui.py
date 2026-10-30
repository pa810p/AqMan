import base64
from datetime import datetime, timezone
from functools import partial

from nicegui import ui
from nicegui.elements.input import Input
from nicegui.events import UploadEventArguments

from aqman.images import MAX_IMAGE_SIZE_BYTES
from aqman.logger import get_logger
from aqman.fertilizer_calculations import (
    calculate_predicted_effects,
    calculate_recommended_dose_ml,
    net_volume_liters,
)
from aqman.models import Aquarium, Fertilizer, FertilizerApplication, WaterChange, WaterSource
from aqman.services import (
    AquariumService,
    FertilizerService,
    NotFoundError,
    ParameterService,
    RecordService,
    ValidationError,
)
from aqman.translations import LANGUAGE_NAMES, translate

logger = get_logger(__name__)


SOURCE_TRANSLATION_KEYS = {
    WaterSource.RO: "water_source_ro",
    WaterSource.TAP: "water_source_tap",
    WaterSource.MIXED: "water_source_mixed",
}

THEME_CSS = """
<style>
html,
body {
    min-height: 100%;
}

body {
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364) fixed !important;
    color: #e7f1f2;
}

.q-layout,
.q-page-container,
.q-page,
.q-tab-panels,
.q-tab-panel {
    background: transparent !important;
}

.q-header {
    background: linear-gradient(110deg, rgba(15, 32, 39, 0.96), rgba(32, 58, 67, 0.94)) !important;
    border-bottom: 1px solid rgba(125, 211, 205, 0.2);
    backdrop-filter: blur(12px);
}

.q-card,
.q-menu,
.q-dialog__inner > .q-card {
    background: rgba(15, 38, 45, 0.9) !important;
    border: 1px solid rgba(125, 211, 205, 0.18);
    border-radius: 18px;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.18);
}

.q-tab {
    color: #b6c9cc;
}

.q-tab--active {
    color: #6bbdb5 !important;
}

.q-tab__indicator {
    background: #398f88 !important;
}

.q-field--outlined .q-field__control:before {
    border-color: rgba(160, 194, 198, 0.38);
}

.q-field--focused .q-field__control:after {
    border-color: #398f88;
}

.q-field__native,
.q-field__input,
.q-field__label {
    color: #e7f1f2;
}

.q-field--filled .q-field__control {
    background: rgba(8, 27, 33, 0.4);
    border-radius: 10px 10px 0 0;
}

.q-table__container {
    background: rgba(15, 38, 45, 0.86);
    border: 1px solid rgba(125, 211, 205, 0.16);
    border-radius: 16px;
    color: #e7f1f2;
}

.q-table thead tr {
    background: rgba(65, 112, 119, 0.28);
}

.q-table tbody tr:hover {
    background: rgba(38, 122, 116, 0.1);
}

.q-separator {
    background: rgba(160, 194, 198, 0.2);
}
</style>
"""


def _local_datetime_parts(value: datetime | None = None) -> tuple[str, str]:
    local_value = value.astimezone() if value is not None else datetime.now().astimezone()
    return local_value.strftime("%Y-%m-%d"), local_value.strftime("%H:%M")


def _parse_local_datetime(date_value: str | None, time_value: str | None) -> datetime:
    if not date_value or not time_value:
        raise ValidationError("Enter a date and time.")
    try:
        parsed = datetime.fromisoformat(f"{date_value}T{time_value}")
    except ValueError as error:
        raise ValidationError("Enter a valid date and time.") from error
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.astimezone(timezone.utc)


def _format_datetime(value: datetime | None, language: str) -> str:
    if value is None:
        return translate(language, "no_measurements")
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


def _image_data_uri(data: bytes, content_type: str = "image/jpeg") -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def _note_preview(content: str) -> str:
    words = content.split()
    if len(words) <= 6:
        return " ".join(words)
    return f"{' '.join(words[:6])}…"


def _notify_error(error: Exception) -> None:
    logger.warning("Handled %s: %s", type(error).__name__, error)
    ui.notify(str(error), type="negative")


def build_ui(
    aquarium_service: AquariumService,
    parameter_service: ParameterService,
    fertilizer_service: FertilizerService,
    record_service: RecordService,
    language: str = "en",
) -> None:
    if language not in LANGUAGE_NAMES:
        language = "en"
    ui.context.client.page.language = "en-US" if language == "en" else "pl"

    def t(key: str, **values: object) -> str:
        return translate(language, key, **values)

    def create_datetime_inputs(value: datetime | None = None) -> tuple[Input, Input]:
        date_value, time_value = _local_datetime_parts(value)
        with ui.row().classes("w-full gap-2"):
            date_input = ui.input(
                t("date"),
                value=date_value,
                placeholder=t("date_format_hint"),
            ).props('mask="####-##-##"').classes("min-w-0 flex-1")
            with date_input.add_slot("append"):
                with ui.menu().props("no-parent-event") as date_menu:
                    date_picker = ui.date(
                        value=date_value,
                        mask="YYYY-MM-DD",
                    )
                ui.icon("event").classes("cursor-pointer").on(
                    "click",
                    lambda: date_menu.open(),
                )
            date_picker.bind_value(date_input)
            time_input = ui.input(
                t("time"),
                value=time_value,
                placeholder="HH:MM",
            ).props('mask="##:##"').classes("min-w-0 flex-1")
        return date_input, time_input

    def reset_datetime_inputs(date_input: Input, time_input: Input) -> None:
        date_input.value, time_input.value = _local_datetime_parts()

    selected_aquarium_id: int | None = None

    def current_aquarium_id() -> int:
        if selected_aquarium_id is None:
            raise ValidationError("Select an aquarium first.")
        return selected_aquarium_id

    ui.colors(
        primary="#267a74",
        secondary="#547b83",
        accent="#5caea5",
        dark="#10272e",
        positive="#65d6a5",
        negative="#ef8080",
        info="#63b8c5",
        warning="#e6bd70",
    )
    ui.dark_mode().enable()
    ui.add_head_html(THEME_CSS)

    def switch_language(target_language: str) -> None:
        if target_language in LANGUAGE_NAMES and target_language != language:
            ui.navigate.to(f"/?lang={target_language}")

    with ui.header().classes("items-center justify-between"):
        ui.label("Aquarium Manager").classes("text-h5")
        ui.label(t("subtitle")).classes("text-sm")
        with ui.row().classes("items-center gap-1"):
            ui.button("🇬🇧", on_click=lambda: switch_language("en")).props("flat round").tooltip("English")
            ui.button("🇵🇱", on_click=lambda: switch_language("pl")).props("flat round").tooltip("Polski")

    with ui.column().classes("w-full max-w-6xl mx-auto p-4"):
        with ui.tabs().classes("w-full") as tabs:
            dashboard_tab = ui.tab(t("tab_dashboard"))
            aquariums_tab = ui.tab(t("tab_aquariums"))
            aquarium_detail_tab = ui.tab(t("tab_aquarium_detail"))
            aquarium_detail_tab.set_visibility(False)
            settings_tab = ui.tab(t("tab_parameters"))

        with ui.tab_panels(tabs, value=dashboard_tab).classes("w-full"):
            with ui.tab_panel(dashboard_tab):
                ui.label(t("active_aquariums")).classes("text-h6")
                dashboard_container = ui.column().classes("w-full")

            with ui.tab_panel(aquarium_detail_tab):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.button(
                        t("back_to_dashboard"),
                        icon="arrow_back",
                        on_click=lambda: show_dashboard(),
                    ).props("flat")
                    ui.button(
                        t("edit_selected"),
                        icon="edit",
                        on_click=lambda: edit_current_aquarium(),
                    )
                aquarium_details_container = ui.column().classes("w-full")
                ui.separator()

                with ui.grid(columns=2).classes("w-full"):
                    with ui.card().classes("w-full"):
                        ui.label(t("add_measurement")).classes("text-h6")
                        measurement_date, measurement_time = create_datetime_inputs()
                        measurement_parameter = ui.select({}, label=t("parameter")).classes("w-full")
                        measurement_value = ui.number(t("value")).classes("w-full")
                        measurement_note = ui.input(t("optional_note")).classes("w-full")
                        ui.button(
                            t("save_measurement"),
                            icon="save",
                            on_click=lambda: save_measurement(),
                        )

                    with ui.card().classes("w-full"):
                        ui.label(t("new_fertilizer_application")).classes("text-h6")
                        fertilizer_application_date, fertilizer_application_time = (
                            create_datetime_inputs()
                        )
                        fertilizer_application_fertilizer = ui.select(
                            {},
                            label=t("fertilizer"),
                        ).classes("w-full")
                        fertilizer_target_parameter = ui.select(
                            {},
                            label=t("fertilizer_target_parameter"),
                        ).classes("w-full")
                        fertilizer_target_increase = ui.number(
                            t("fertilizer_target_increase"),
                            value=5,
                            min=0.1,
                        ).classes("w-full")
                        fertilizer_recommended_dose = ui.label(
                            t("fertilizer_dose_unavailable")
                        ).classes("text-body2")
                        fertilizer_actual_dose = ui.number(
                            t("fertilizer_actual_dose"),
                            min=0,
                        ).classes("w-full")
                        fertilizer_other_effects = ui.label(
                            t("fertilizer_effects_unavailable")
                        ).classes("text-body2")
                        fertilizer_application_notes = ui.textarea(
                            t("optional_note")
                        ).classes("w-full")
                        ui.button(
                            t("save_fertilizer_application"),
                            icon="save",
                            on_click=lambda: save_fertilizer_application(),
                        )

                    with ui.card().classes("w-full"):
                        ui.label(t("new_note")).classes("text-h6")
                        note_date, note_time = create_datetime_inputs()
                        note_category = ui.input(t("optional_category")).classes("w-full")
                        note_content = ui.textarea(t("note_content")).classes("w-full")
                        ui.button(t("save_note"), icon="save", on_click=lambda: save_note())

                    with ui.card().classes("w-full"):
                        ui.label(t("new_water_change")).classes("text-h6")
                        water_change_date, water_change_time = create_datetime_inputs()
                        water_source = ui.select(
                            {
                                source.value: t(translation_key)
                                for source, translation_key in SOURCE_TRANSLATION_KEYS.items()
                            },
                            label=t("water_source"),
                            value=WaterSource.RO.value,
                        ).classes("w-full")
                        water_volume = ui.number(t("water_volume"), min=0).classes("w-full")
                        water_description = ui.textarea(t("optional_description")).classes("w-full")
                        ui.button(
                            t("save_water_change"),
                            icon="save",
                            on_click=lambda: save_water_change(),
                        )

                    with ui.card().classes("w-full col-span-2"):
                        ui.label(t("activity_history")).classes("text-h6")
                        history_container = ui.column().classes("w-full")

            with ui.tab_panel(aquariums_tab):
                with ui.row().classes("items-center"):
                    ui.label(t("tab_aquariums")).classes("text-h6")
                    ui.button(t("add_aquarium"), icon="add", on_click=lambda: open_aquarium_dialog())
                aquariums_container = ui.column().classes("w-full")

            with ui.tab_panel(settings_tab):
                with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2 gap-4 w-full"):
                    with ui.card().classes("w-full"):
                        with ui.row().classes("items-center"):
                            ui.label(t("parameter_definitions")).classes("text-h6")
                            ui.button(
                                t("add_parameter"),
                                icon="add",
                                on_click=lambda: open_parameter_dialog(),
                            )
                        ui.label(t("parameter_hint")).classes("text-body2")
                        parameters_container = ui.column().classes("w-full")

                    with ui.card().classes("w-full"):
                        with ui.row().classes("items-center"):
                            ui.label(t("fertilizer_catalog")).classes("text-h6")
                            ui.button(
                                t("add_fertilizer"),
                                icon="add",
                                on_click=lambda: open_fertilizer_dialog(),
                            )
                        fertilizers_container = ui.column().classes("w-full")

    def show_dashboard() -> None:
        nonlocal selected_aquarium_id
        selected_aquarium_id = None
        tabs.value = dashboard_tab
        aquarium_detail_tab.set_visibility(False)
        tabs.update()

    def open_aquarium_details(aquarium_id: int) -> None:
        nonlocal selected_aquarium_id
        selected_aquarium_id = aquarium_id
        aquarium_detail_tab.set_visibility(True)
        refresh_all()
        tabs.value = aquarium_detail_tab
        tabs.update()

    def edit_current_aquarium() -> None:
        try:
            aquarium_id = current_aquarium_id()
        except ValidationError as error:
            _notify_error(error)
            return
        aquarium = next(
            (item for item in aquarium_service.list_aquariums() if item.id == aquarium_id),
            None,
        )
        if aquarium is None:
            ui.notify(t("aquarium_not_found"), type="negative")
            return
        open_aquarium_dialog(aquarium)

    def refresh_dashboard() -> None:
        dashboard_container.clear()
        with dashboard_container:
            dashboard = aquarium_service.dashboard()
            if not dashboard:
                ui.label(t("empty_dashboard"))
                return
            with ui.row().classes("w-full"):
                for item in dashboard:
                    open_aquarium = partial(open_aquarium_details, item.aquarium.id)
                    with ui.card().classes("min-w-64 w-72"):
                        if item.aquarium.thumbnail_data:
                            ui.image(_image_data_uri(item.aquarium.thumbnail_data)).classes(
                                "w-full h-40 rounded-lg object-cover cursor-pointer"
                            ).on("click", open_aquarium).tooltip(t("open_aquarium"))
                        else:
                            placeholder = ui.column().classes(
                                "w-full h-40 items-center justify-center rounded-lg bg-slate-800"
                                " cursor-pointer"
                            ).on("click", open_aquarium).tooltip(t("open_aquarium"))
                            with placeholder:
                                ui.icon("image", size="48px").classes("text-teal-300")
                                ui.label(t("no_photo")).classes("text-caption")
                        ui.label(item.aquarium.name).classes("text-h6")
                        ui.label(t("volume", volume=item.aquarium.volume_liters))
                        if item.aquarium.description:
                            ui.label(item.aquarium.description)
                        ui.label(
                            t(
                                "last_measurement",
                                timestamp=_format_datetime(item.last_measurement_at, language),
                            )
                        )
                        ui.button(
                            t("open_aquarium"),
                            icon="arrow_forward",
                            on_click=lambda aquarium_id=item.aquarium.id: open_aquarium_details(aquarium_id),
                        ).props("flat")

    def refresh_aquarium_details() -> None:
        aquarium_details_container.clear()
        with aquarium_details_container:
            if selected_aquarium_id is None:
                ui.label(t("choose_aquarium_details"))
                return
            aquarium = next(
                (item for item in aquarium_service.list_aquariums() if item.id == selected_aquarium_id),
                None,
            )
            if aquarium is None:
                ui.label(t("aquarium_not_found"))
                return
            with ui.card().classes("w-full"):
                with ui.row().classes("w-full items-center justify-between gap-6"):
                    with ui.column().classes("gap-1"):
                        ui.label(aquarium.name).classes("text-h4")
                        ui.label(t("volume", volume=aquarium.volume_liters))
                        if aquarium.description:
                            ui.label(aquarium.description)
                        if not aquarium.active:
                            ui.label(t("status_archived")).classes("text-caption")
                    if aquarium.thumbnail_data:
                        ui.image(_image_data_uri(aquarium.thumbnail_data)).classes(
                            "ml-auto h-32 w-48 shrink-0 rounded-lg object-cover"
                        )
                    else:
                        with ui.column().classes(
                            "ml-auto h-32 w-48 shrink-0 items-center justify-center rounded-lg bg-slate-800"
                        ):
                            ui.icon("image", size="40px").classes("text-teal-300")
                            ui.label(t("no_photo")).classes("text-caption")

    def refresh_aquariums() -> None:
        aquariums_container.clear()
        with aquariums_container:
            aquariums = aquarium_service.list_aquariums()
            if not aquariums:
                ui.label(t("empty_aquariums"))
                return
            for aquarium in aquariums:
                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.column().classes("gap-0"):
                            ui.label(aquarium.name).classes("text-subtitle1")
                            ui.label(
                                t(
                                    "aquarium_summary",
                                    volume=aquarium.volume_liters,
                                    status=t("status_active") if aquarium.active else t("status_archived"),
                                )
                            )
                            if aquarium.description:
                                ui.label(aquarium.description).classes("text-body2")
                        with ui.row():
                            ui.button(
                                t("edit_selected"),
                                icon="edit",
                                on_click=lambda item=aquarium: open_aquarium_dialog(item),
                            ).props("flat")
                            ui.button(
                                t("archive") if aquarium.active else t("restore"),
                                icon="archive" if aquarium.active else "unarchive",
                                on_click=lambda aquarium_id=aquarium.id, active=not aquarium.active: toggle_aquarium(
                                    aquarium_id, active
                                ),
                            )

    fertilizer_cache: dict[int, Fertilizer] = {}

    def refresh_parameters() -> None:
        parameters = parameter_service.list_parameters()
        parameters_container.clear()
        options = {
            parameter.id: f"{parameter.name} ({parameter.unit})"
            for parameter in parameters
        }
        try:
            previous_parameter_id = int(measurement_parameter.value)
        except (TypeError, ValueError):
            previous_parameter_id = None
        measurement_parameter.options = options
        measurement_parameter.value = (
            previous_parameter_id
            if previous_parameter_id in options
            else next(iter(options), None)
        )
        measurement_parameter.update()
        with parameters_container:
            if not parameters:
                ui.label(t("empty_parameters"))
            else:
                ui.table(
                    columns=[
                        {"name": "name", "label": t("parameter"), "field": "name", "align": "left"},
                        {"name": "unit", "label": t("table_unit"), "field": "unit", "align": "left"},
                        {"name": "description", "label": t("description"), "field": "description", "align": "left"},
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

    def refresh_fertilizers() -> None:
        nonlocal fertilizer_cache
        fertilizers = fertilizer_service.list_fertilizers()
        fertilizer_cache = {fertilizer.id: fertilizer for fertilizer in fertilizers}
        fertilizer_options = {
            fertilizer.id: fertilizer.name for fertilizer in fertilizers
        }
        try:
            previous_fertilizer_id = int(fertilizer_application_fertilizer.value)
        except (TypeError, ValueError):
            previous_fertilizer_id = None
        fertilizer_application_fertilizer.options = fertilizer_options
        fertilizer_application_fertilizer.value = (
            previous_fertilizer_id
            if previous_fertilizer_id in fertilizer_options
            else next(iter(fertilizer_options), None)
        )
        fertilizer_application_fertilizer.update()
        refresh_fertilizer_application_parameters()
        fertilizers_container.clear()
        with fertilizers_container:
            if not fertilizers:
                ui.label(t("empty_fertilizers"))
                return
            for fertilizer in fertilizers:
                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-start justify-between"):
                        with ui.column().classes("gap-1"):
                            ui.label(fertilizer.name).classes("text-subtitle1")
                            ui.label(
                                t("fertilizer_dose_summary", dose=fertilizer.dose_ml_per_100l)
                            ).classes("text-body2")
                        with ui.row().classes("items-center"):
                            ui.button(
                                t("edit_fertilizer"),
                                icon="edit",
                                on_click=lambda fertilizer_id=fertilizer.id: open_fertilizer_dialog(
                                    fertilizer_id
                                ),
                            ).props("flat")
                            ui.button(
                                t("delete_fertilizer"),
                                icon="delete",
                                on_click=lambda fertilizer_id=fertilizer.id, name=fertilizer.name: confirm_delete_fertilizer(
                                    fertilizer_id,
                                    name,
                                ),
                            ).props("flat")
                    ui.separator()
                    with ui.column().classes("w-full gap-1"):
                        for effect in fertilizer.effects:
                            ui.label(
                                t(
                                    "fertilizer_effect_line",
                                    parameter=f"{effect.parameter.name} ({effect.parameter.unit})",
                                    ppm=effect.ppm_per_dose,
                                )
                            )

    def refresh_fertilizer_application_parameters() -> None:
        fertilizer = _selected_fertilizer_application_fertilizer()
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
            previous_parameter_id = int(fertilizer_target_parameter.value)
        except (TypeError, ValueError):
            previous_parameter_id = None
        fertilizer_target_parameter.options = effect_options
        fertilizer_target_parameter.value = (
            previous_parameter_id
            if previous_parameter_id in effect_options
            else next(iter(effect_options), None)
        )
        fertilizer_target_parameter.update()
        refresh_fertilizer_application_recommendation()

    def _selected_fertilizer_application_fertilizer() -> Fertilizer | None:
        try:
            fertilizer_id = int(fertilizer_application_fertilizer.value)
        except (TypeError, ValueError):
            return None
        return fertilizer_cache.get(fertilizer_id)

    def refresh_fertilizer_application_recommendation() -> None:
        fertilizer = _selected_fertilizer_application_fertilizer()
        if fertilizer is None:
            fertilizer_recommended_dose.text = t("fertilizer_dose_unavailable")
            fertilizer_actual_dose.value = None
            fertilizer_actual_dose.update()
            refresh_fertilizer_application_effect_preview()
            return
        try:
            aquarium_id = current_aquarium_id()
            aquarium = next(
                (
                    item
                    for item in aquarium_service.list_aquariums()
                    if item.id == aquarium_id
                ),
                None,
            )
            if aquarium is None:
                raise NotFoundError("Aquarium not found.")
            target_parameter_id = int(fertilizer_target_parameter.value)
            target_effect = next(
                effect
                for effect in fertilizer.effects
                if effect.parameter_id == target_parameter_id
            )
            recommended_dose = calculate_recommended_dose_ml(
                gross_volume_liters=aquarium.volume_liters,
                dose_ml_per_100l=fertilizer.dose_ml_per_100l,
                target_effect_ppm_per_dose=target_effect.ppm_per_dose,
                target_increase_ppm=fertilizer_target_increase.value,
            )
            net_volume = net_volume_liters(aquarium.volume_liters)
        except (StopIteration, TypeError, ValueError, ValidationError, NotFoundError):
            fertilizer_recommended_dose.text = t("fertilizer_dose_unavailable")
            fertilizer_actual_dose.value = None
            fertilizer_actual_dose.update()
            refresh_fertilizer_application_effect_preview()
            return
        fertilizer_recommended_dose.text = t(
            "fertilizer_recommended_dose",
            dose=recommended_dose,
            net_volume=net_volume,
        )
        fertilizer_actual_dose.value = recommended_dose
        fertilizer_actual_dose.update()
        refresh_fertilizer_application_effect_preview()

    def refresh_fertilizer_application_effect_preview() -> None:
        fertilizer = _selected_fertilizer_application_fertilizer()
        if fertilizer is None:
            fertilizer_other_effects.text = t("fertilizer_effects_unavailable")
            return
        try:
            aquarium_id = current_aquarium_id()
            aquarium = next(
                (
                    item
                    for item in aquarium_service.list_aquariums()
                    if item.id == aquarium_id
                ),
                None,
            )
            if aquarium is None:
                raise NotFoundError("Aquarium not found.")
            predicted_effects = calculate_predicted_effects(
                gross_volume_liters=aquarium.volume_liters,
                dose_ml_per_100l=fertilizer.dose_ml_per_100l,
                actual_dose_ml=fertilizer_actual_dose.value,
                effects={
                    effect.parameter_id: effect.ppm_per_dose
                    for effect in fertilizer.effects
                },
            )
            target_parameter_id = int(fertilizer_target_parameter.value)
        except (TypeError, ValueError, ValidationError, NotFoundError):
            fertilizer_other_effects.text = t("fertilizer_effects_unavailable")
            return
        remaining_effects = [
            t(
                "fertilizer_effect_line",
                parameter=next(
                    effect.parameter.name
                    for effect in fertilizer.effects
                    if effect.parameter_id == parameter_id
                ),
                ppm=ppm,
            )
            for parameter_id, ppm in predicted_effects.items()
            if parameter_id != target_parameter_id
        ]
        fertilizer_other_effects.text = (
            "; ".join(remaining_effects) if remaining_effects else t("no_other_fertilizer_effects")
        )

    fertilizer_application_fertilizer.on_value_change(
        lambda _: refresh_fertilizer_application_parameters()
    )
    fertilizer_target_parameter.on_value_change(
        lambda _: refresh_fertilizer_application_recommendation()
    )
    fertilizer_target_increase.on_value_change(
        lambda _: refresh_fertilizer_application_recommendation()
    )
    fertilizer_actual_dose.on_value_change(
        lambda _: refresh_fertilizer_application_effect_preview()
    )

    def open_note_dialog(note_id: int) -> None:
        try:
            aquarium_id = current_aquarium_id()
            note = record_service.get_note(aquarium_id, note_id)
        except (ValidationError, NotFoundError) as error:
            _notify_error(error)
            return

        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label(t("edit_note_dialog")).classes("text-h6")
            date_input, time_input = create_datetime_inputs(note.timestamp)
            category_input = ui.input(
                t("optional_category"),
                value=note.category or "",
            ).classes("w-full")
            content_input = ui.textarea(
                t("note_content"),
                value=note.content,
            ).classes("w-full")

            def save() -> None:
                try:
                    record_service.update_note(
                        aquarium_id,
                        note.id,
                        _parse_local_datetime(date_input.value, time_input.value),
                        category_input.value,
                        content_input.value or "",
                    )
                except (ValidationError, NotFoundError) as error:
                    _notify_error(error)
                    return
                dialog.close()
                ui.notify(t("updated_note"), type="positive")
                refresh_all()

            with ui.row().classes("justify-end"):
                ui.button(t("cancel"), on_click=dialog.close).props("flat")
                ui.button(t("save"), on_click=save, icon="save")
        dialog.open()

    def refresh_history() -> None:
        history_container.clear()
        with history_container:
            try:
                aquarium_id = current_aquarium_id()
            except ValidationError:
                ui.label(t("empty_history"))
                return

            daily_history = record_service.daily_history(aquarium_id)
            if not daily_history:
                ui.label(t("empty_history"))
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
                    "label": t("history_date"),
                    "field": "date",
                    "align": "left",
                },
                *[
                    {
                        "name": f"parameter_{parameter_id}",
                        "label": f"{parameter_details[parameter_id][0]} ({parameter_details[parameter_id][1]})",
                        "field": f"parameter_{parameter_id}",
                        "align": "right",
                    }
                    for parameter_id in parameter_ids
                ],
                {
                    "name": "fertilizer_applications",
                    "label": t("history_fertilizer_applications"),
                    "field": "fertilizer_applications",
                    "align": "left",
                },
                {
                    "name": "water_changes",
                    "label": t("history_water_changes"),
                    "field": "water_changes",
                    "align": "left",
                },
                {
                    "name": "notes",
                    "label": t("history_notes"),
                    "field": "notes",
                    "align": "left",
                },
            ]

            def format_water_change(water_change: WaterChange) -> str:
                entry = t(
                    "history_water_change_entry",
                    source=t(SOURCE_TRANSLATION_KEYS[water_change.source]),
                    volume=water_change.volume_liters,
                )
                if water_change.description:
                    return f"{entry} ({water_change.description})"
                return entry

            def format_fertilizer_application(
                application: FertilizerApplication,
            ) -> str:
                return t(
                    "history_fertilizer_application_entry",
                    name=application.fertilizer.name,
                    dose=application.actual_dose_ml,
                )

            rows = []
            for day in daily_history:
                note_links = [
                    {
                        "id": f"note-{note.id}",
                        "preview": _note_preview(note.content),
                        "content": note.content,
                    }
                    for note in day.notes
                ]
                note_links.extend(
                    {
                        "id": f"measurement-{measurement.id}",
                        "preview": _note_preview(measurement.note),
                        "content": measurement.note,
                    }
                    for measurements in day.measurements.values()
                    for measurement in measurements
                    if measurement.note
                )
                note_links.extend(
                    {
                        "id": f"fertilizer-application-{application.id}",
                        "preview": _note_preview(application.notes),
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
                            "label": format_water_change(water_change),
                        }
                        for water_change in day.water_changes
                    ],
                    "fertilizer_applications": [
                        {
                            "id": application.id,
                            "label": format_fertilizer_application(application),
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
                rows.append(row)

            history_table = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")
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
                        "__EDIT_LABEL__", t("edit_measurement")
                    ),
                )
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
                """.replace("__EDIT_LABEL__", t("edit_fertilizer_application")),
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
                """.replace("__EDIT_LABEL__", t("edit_water_change")),
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

            def handle_note_edit(event) -> None:
                note_type, separator, identifier = str(event.args).rpartition("-")
                if not separator:
                    _notify_error(NotFoundError("Note not found."))
                    return
                try:
                    record_id = int(identifier)
                except ValueError:
                    _notify_error(NotFoundError("Note not found."))
                    return
                if note_type == "note":
                    open_note_dialog(record_id)
                elif note_type == "measurement":
                    open_measurement_dialog(record_id)
                elif note_type == "fertilizer-application":
                    open_fertilizer_application_dialog(record_id)
                else:
                    _notify_error(NotFoundError("Note not found."))

            history_table.on("note-edit-click", handle_note_edit)

            def handle_measurement_edit(event) -> None:
                try:
                    measurement_id = int(event.args)
                except (TypeError, ValueError):
                    _notify_error(NotFoundError("Measurement not found."))
                    return
                open_measurement_dialog(measurement_id)

            history_table.on(
                "measurement-edit-click",
                handle_measurement_edit,
            )

            def handle_water_change_edit(event) -> None:
                try:
                    water_change_id = int(event.args)
                except (TypeError, ValueError):
                    _notify_error(NotFoundError("Water change not found."))
                    return
                open_water_change_dialog(water_change_id)

            history_table.on("water-change-edit-click", handle_water_change_edit)

            def handle_fertilizer_application_edit(event) -> None:
                try:
                    application_id = int(event.args)
                except (TypeError, ValueError):
                    _notify_error(NotFoundError("Fertilizer application not found."))
                    return
                open_fertilizer_application_dialog(application_id)

            history_table.on(
                "fertilizer-application-edit-click",
                handle_fertilizer_application_edit,
            )

    def refresh_all() -> None:
        refresh_dashboard()
        refresh_aquariums()
        refresh_parameters()
        refresh_fertilizers()
        refresh_aquarium_details()
        refresh_history()

    def open_aquarium_dialog(aquarium: Aquarium | None = None) -> None:
        thumbnail_data = aquarium.thumbnail_data if aquarium else None
        thumbnail_changed = False

        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label(t("edit_aquarium_dialog") if aquarium else t("add_aquarium_dialog")).classes("text-h6")
            name_input = ui.input(t("name"), value=aquarium.name if aquarium else "").classes("w-full")
            volume_input = ui.number(
                t("aquarium_volume"),
                value=aquarium.volume_liters if aquarium else None,
                min=0,
            ).classes("w-full")
            description_input = ui.textarea(
                t("description"),
                value=aquarium.description if aquarium else "",
            ).classes("w-full")

            ui.label(t("aquarium_photo")).classes("text-subtitle1")
            image_preview = ui.image("").classes("w-full h-48 rounded-lg object-cover")
            image_preview.set_visibility(thumbnail_data is not None)
            image_placeholder = ui.label(t("no_photo")).classes("text-body2")
            image_placeholder.set_visibility(thumbnail_data is None)
            if thumbnail_data is not None:
                image_preview.set_source(_image_data_uri(thumbnail_data))

            async def receive_image(event: UploadEventArguments) -> None:
                nonlocal thumbnail_data, thumbnail_changed
                thumbnail_data = await event.file.read()
                thumbnail_changed = True
                image_preview.set_source(
                    _image_data_uri(thumbnail_data, event.file.content_type or "image/jpeg")
                )
                image_preview.set_visibility(True)
                image_placeholder.set_visibility(False)
                remove_photo_button.set_visibility(True)

            def remove_thumbnail() -> None:
                nonlocal thumbnail_data, thumbnail_changed
                thumbnail_data = None
                thumbnail_changed = True
                image_preview.set_visibility(False)
                image_placeholder.set_visibility(True)
                remove_photo_button.set_visibility(False)

            ui.upload(
                label=t("upload_photo"),
                auto_upload=True,
                max_file_size=MAX_IMAGE_SIZE_BYTES,
                on_upload=receive_image,
                on_rejected=lambda: ui.notify(t("image_upload_rejected"), type="negative"),
            ).props('accept=".jpg,.jpeg,.png,.webp"').classes("w-full")
            remove_photo_button = ui.button(
                t("remove_photo"),
                icon="delete",
                on_click=remove_thumbnail,
            ).props("flat")
            remove_photo_button.set_visibility(thumbnail_data is not None)

            def save() -> None:
                try:
                    if aquarium is None:
                        aquarium_service.create_aquarium(
                            name_input.value or "",
                            volume_input.value,
                            description_input.value,
                            thumbnail_data=thumbnail_data if thumbnail_changed else None,
                        )
                    else:
                        aquarium_service.update_aquarium(
                            aquarium.id,
                            name_input.value or "",
                            volume_input.value,
                            description_input.value,
                            thumbnail_data=thumbnail_data if thumbnail_changed else None,
                            clear_thumbnail=thumbnail_changed and thumbnail_data is None,
                        )
                except (ValidationError, NotFoundError) as error:
                    _notify_error(error)
                    return
                dialog.close()
                ui.notify(t("saved_aquarium"), type="positive")
                refresh_all()

            with ui.row().classes("justify-end"):
                ui.button(t("cancel"), on_click=dialog.close).props("flat")
                ui.button(t("save"), on_click=save, icon="save")
        dialog.open()

    def toggle_aquarium(aquarium_id: int, active: bool) -> None:
        try:
            aquarium_service.set_active(aquarium_id, active)
        except NotFoundError as error:
            _notify_error(error)
            return
        refresh_all()

    def open_parameter_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label(t("add_parameter_dialog")).classes("text-h6")
            name_input = ui.input(t("parameter_name_hint")).classes("w-full")
            unit_input = ui.input(t("unit_hint")).classes("w-full")
            description_input = ui.textarea(t("optional_description")).classes("w-full")

            def save() -> None:
                try:
                    parameter_service.create_parameter(
                        name_input.value or "",
                        unit_input.value or "",
                        description_input.value,
                    )
                except ValidationError as error:
                    _notify_error(error)
                    return
                dialog.close()
                ui.notify(t("saved_parameter"), type="positive")
                refresh_all()

            with ui.row().classes("justify-end"):
                ui.button(t("cancel"), on_click=dialog.close).props("flat")
                ui.button(t("save"), on_click=save, icon="save")
        dialog.open()

    def open_fertilizer_dialog(fertilizer_id: int | None = None) -> None:
        fertilizer: Fertilizer | None = None
        if fertilizer_id is not None:
            try:
                fertilizer = fertilizer_service.get_fertilizer(fertilizer_id)
            except NotFoundError as error:
                _notify_error(error)
                return

        parameters = fertilizer_service.list_effect_parameters()
        parameter_by_id = {parameter.id: parameter for parameter in parameters}
        parameter_options = {
            parameter.id: f"{parameter.name} ({parameter.unit})"
            for parameter in parameters
        }

        with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl"):
            ui.label(
                t("edit_fertilizer_dialog") if fertilizer else t("add_fertilizer_dialog")
            ).classes("text-h6")
            name_input = ui.input(
                t("fertilizer_name"),
                value=fertilizer.name if fertilizer else "",
            ).classes("w-full")
            dose_input = ui.number(
                t("fertilizer_dose"),
                value=fertilizer.dose_ml_per_100l if fertilizer else None,
                min=0,
            ).classes("w-full")
            ui.label(t("fertilizer_effects")).classes("text-subtitle1")
            if not parameters:
                ui.label(t("no_fertilizer_parameters")).classes("text-body2")
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
                        if (other_id := parameter_id_for(other_input.value)) in parameter_by_id
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
                            label=t("fertilizer_effect_parameter"),
                            value=parameter_id,
                        ).classes("min-w-0 flex-1")
                        ppm_input = ui.number(
                            t("fertilizer_effect_ppm"),
                            value=ppm_per_dose,
                            min=0,
                        ).classes("min-w-0 flex-1")
                        remove_button = ui.button(
                            icon="close",
                            on_click=lambda: remove_effect_row(row),
                        ).props("flat round").tooltip(t("remove_fertilizer_effect"))
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
                t("add_fertilizer_effect"),
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
                        fertilizer_service.update_fertilizer(
                            fertilizer.id,
                            name_input.value or "",
                            dose,
                            effects,
                        )
                    else:
                        fertilizer_service.create_fertilizer(
                            name_input.value or "",
                            dose,
                            effects,
                        )
                except (NotFoundError, ValidationError, TypeError, ValueError) as error:
                    if isinstance(error, (TypeError, ValueError)) and not isinstance(
                        error, ValidationError
                    ):
                        error = ValidationError("Enter valid fertilizer values.")
                    _notify_error(error)
                    return
                dialog.close()
                ui.notify(t("saved_fertilizer"), type="positive")
                refresh_all()

            with ui.row().classes("justify-end"):
                ui.button(t("cancel"), on_click=dialog.close).props("flat")
                ui.button(t("save"), on_click=save, icon="save")
        dialog.open()

    def confirm_delete_fertilizer(fertilizer_id: int, name: str) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-md"):
            ui.label(t("confirm_delete_fertilizer", name=name))

            def delete() -> None:
                try:
                    fertilizer_service.delete_fertilizer(fertilizer_id)
                except (NotFoundError, ValidationError) as error:
                    _notify_error(error)
                    dialog.close()
                    refresh_fertilizers()
                    return
                dialog.close()
                ui.notify(t("deleted_fertilizer"), type="positive")
                refresh_all()

            with ui.row().classes("justify-end"):
                ui.button(t("cancel"), on_click=dialog.close).props("flat")
                ui.button(
                    t("delete_fertilizer"),
                    icon="delete",
                    on_click=delete,
                ).props("color=negative")
        dialog.open()

    def open_measurement_dialog(measurement_id: int) -> None:
        try:
            aquarium_id = current_aquarium_id()
            measurement = record_service.get_measurement(aquarium_id, measurement_id)
        except (ValidationError, NotFoundError) as error:
            _notify_error(error)
            return

        parameter_options = {
            parameter.id: f"{parameter.name} ({parameter.unit})"
            for parameter in parameter_service.list_parameters()
        }
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label(t("edit_measurement_dialog")).classes("text-h6")
            date_input, time_input = create_datetime_inputs(measurement.timestamp)
            parameter_input = ui.select(
                parameter_options,
                label=t("parameter"),
                value=measurement.parameter_id,
            ).classes("w-full")
            value_input = ui.number(t("value"), value=measurement.value).classes("w-full")
            note_input = ui.input(
                t("optional_note"),
                value=measurement.note or "",
            ).classes("w-full")

            def save() -> None:
                try:
                    try:
                        parameter_id = int(parameter_input.value)
                    except (TypeError, ValueError) as error:
                        raise ValidationError("Select a parameter first.") from error
                    record_service.update_measurement(
                        aquarium_id,
                        measurement.id,
                        _parse_local_datetime(date_input.value, time_input.value),
                        parameter_id,
                        value_input.value,
                        note_input.value,
                    )
                except (ValidationError, NotFoundError) as error:
                    _notify_error(error)
                    return
                dialog.close()
                ui.notify(t("updated_measurement"), type="positive")
                refresh_all()

            with ui.row().classes("justify-end"):
                ui.button(t("cancel"), on_click=dialog.close).props("flat")
                ui.button(t("save"), on_click=save, icon="save")
        dialog.open()

    def open_fertilizer_application_dialog(application_id: int) -> None:
        try:
            aquarium_id = current_aquarium_id()
            application = record_service.get_fertilizer_application(
                aquarium_id,
                application_id,
            )
        except (ValidationError, NotFoundError) as error:
            _notify_error(error)
            return

        fertilizers = fertilizer_service.list_fertilizers()
        fertilizer_options = {
            fertilizer.id: fertilizer.name for fertilizer in fertilizers
        }
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label(t("edit_fertilizer_application")).classes("text-h6")
            date_input, time_input = create_datetime_inputs(application.timestamp)
            fertilizer_input = ui.select(
                fertilizer_options,
                label=t("fertilizer"),
                value=application.fertilizer_id,
            ).classes("w-full")
            dose_input = ui.number(
                t("fertilizer_actual_dose"),
                value=application.actual_dose_ml,
                min=0,
            ).classes("w-full")
            notes_input = ui.textarea(
                t("optional_note"),
                value=application.notes or "",
            ).classes("w-full")

            def save() -> None:
                try:
                    try:
                        fertilizer_id = int(fertilizer_input.value)
                    except (TypeError, ValueError) as error:
                        raise ValidationError("Select a fertilizer first.") from error
                    record_service.update_fertilizer_application(
                        aquarium_id,
                        application.id,
                        _parse_local_datetime(date_input.value, time_input.value),
                        fertilizer_id,
                        dose_input.value,
                        notes_input.value,
                    )
                except (ValidationError, NotFoundError) as error:
                    _notify_error(error)
                    return
                dialog.close()
                ui.notify(t("updated_fertilizer_application"), type="positive")
                refresh_all()

            def confirm_delete() -> None:
                with ui.dialog() as confirmation, ui.card().classes("w-full max-w-md"):
                    ui.label(t("confirm_delete_fertilizer_application"))

                    def delete() -> None:
                        try:
                            record_service.delete_fertilizer_application(
                                aquarium_id,
                                application.id,
                            )
                        except (ValidationError, NotFoundError) as error:
                            _notify_error(error)
                            confirmation.close()
                            return
                        confirmation.close()
                        dialog.close()
                        ui.notify(t("deleted_fertilizer_application"), type="positive")
                        refresh_all()

                    with ui.row().classes("justify-end"):
                        ui.button(t("cancel"), on_click=confirmation.close).props("flat")
                        ui.button(
                            t("delete_fertilizer_application"),
                            icon="delete",
                            on_click=delete,
                        ).props("color=negative")
                confirmation.open()

            with ui.row().classes("w-full justify-between"):
                ui.button(
                    t("delete_fertilizer_application"),
                    icon="delete",
                    on_click=confirm_delete,
                ).props("color=negative flat")
                with ui.row().classes("justify-end"):
                    ui.button(t("cancel"), on_click=dialog.close).props("flat")
                    ui.button(t("save"), on_click=save, icon="save")
        dialog.open()

    def open_water_change_dialog(water_change_id: int) -> None:
        try:
            aquarium_id = current_aquarium_id()
            water_change = record_service.get_water_change(aquarium_id, water_change_id)
        except (ValidationError, NotFoundError) as error:
            _notify_error(error)
            return

        source_options = {
            source.value: t(translation_key)
            for source, translation_key in SOURCE_TRANSLATION_KEYS.items()
        }
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
            ui.label(t("edit_water_change_dialog")).classes("text-h6")
            date_input, time_input = create_datetime_inputs(water_change.timestamp)
            source_input = ui.select(
                source_options,
                label=t("water_source"),
                value=water_change.source.value,
            ).classes("w-full")
            volume_input = ui.number(
                t("water_volume"),
                value=water_change.volume_liters,
                min=0,
            ).classes("w-full")
            description_input = ui.textarea(
                t("optional_description"),
                value=water_change.description or "",
            ).classes("w-full")

            def save() -> None:
                try:
                    try:
                        source = WaterSource(source_input.value)
                    except (TypeError, ValueError) as error:
                        raise ValidationError("Select a valid water source.") from error
                    record_service.update_water_change(
                        aquarium_id,
                        water_change.id,
                        _parse_local_datetime(date_input.value, time_input.value),
                        source,
                        volume_input.value,
                        description_input.value,
                    )
                except (ValidationError, NotFoundError) as error:
                    _notify_error(error)
                    return
                dialog.close()
                ui.notify(t("updated_water_change"), type="positive")
                refresh_all()

            with ui.row().classes("justify-end"):
                ui.button(t("cancel"), on_click=dialog.close).props("flat")
                ui.button(t("save"), on_click=save, icon="save")
        dialog.open()

    def save_measurement() -> None:
        try:
            aquarium_id = current_aquarium_id()
            try:
                parameter_id = int(measurement_parameter.value)
            except (TypeError, ValueError) as error:
                raise ValidationError("Select a parameter first.") from error
            record_service.record_measurement(
                aquarium_id,
                _parse_local_datetime(measurement_date.value, measurement_time.value),
                parameter_id,
                measurement_value.value,
                measurement_note.value,
            )
        except (ValidationError, NotFoundError) as error:
            _notify_error(error)
            return
        measurement_value.value = None
        measurement_note.value = ""
        reset_datetime_inputs(measurement_date, measurement_time)
        ui.notify(t("saved_measurement"), type="positive")
        refresh_all()

    def save_note() -> None:
        try:
            record_service.add_note(
                current_aquarium_id(),
                _parse_local_datetime(note_date.value, note_time.value),
                note_category.value,
                note_content.value or "",
            )
        except (ValidationError, NotFoundError) as error:
            _notify_error(error)
            return
        note_category.value = ""
        note_content.value = ""
        reset_datetime_inputs(note_date, note_time)
        ui.notify(t("saved_note"), type="positive")
        refresh_all()

    def save_water_change() -> None:
        try:
            source = WaterSource(water_source.value)
        except ValueError:
            _notify_error(ValidationError("Select a valid water source."))
            return
        try:
            record_service.add_water_change(
                current_aquarium_id(),
                _parse_local_datetime(water_change_date.value, water_change_time.value),
                source,
                water_volume.value,
                water_description.value,
            )
        except (ValidationError, NotFoundError) as error:
            _notify_error(error)
            return
        water_volume.value = None
        water_description.value = ""
        reset_datetime_inputs(water_change_date, water_change_time)
        ui.notify(t("saved_water_change"), type="positive")
        refresh_all()

    def save_fertilizer_application() -> None:
        try:
            try:
                fertilizer_id = int(fertilizer_application_fertilizer.value)
            except (TypeError, ValueError) as error:
                raise ValidationError("Select a fertilizer first.") from error
            record_service.add_fertilizer_application(
                current_aquarium_id(),
                _parse_local_datetime(
                    fertilizer_application_date.value,
                    fertilizer_application_time.value,
                ),
                fertilizer_id,
                fertilizer_actual_dose.value,
                fertilizer_application_notes.value,
            )
        except (ValidationError, NotFoundError) as error:
            _notify_error(error)
            return
        fertilizer_application_notes.value = ""
        reset_datetime_inputs(
            fertilizer_application_date,
            fertilizer_application_time,
        )
        ui.notify(t("saved_fertilizer_application"), type="positive")
        refresh_all()

    refresh_all()
