from datetime import datetime
from functools import partial

from nicegui import ui

from aqman.logger import get_logger
from aqman.models import (
    WaterSource,
)
from aqman.services import (
    AquariumService,
    FertilizerService,
    NotFoundError,
    ParameterService,
    RecordService,
    ValidationError,
)
from aqman.translations import LANGUAGE_NAMES, translate
from aqman.ui.components import (
    ActivityHistory,
    AquariumDialog,
    FertilizerCatalog,
    FertilizerApplicationForm,
    MeasurementChart,
    MeasurementForm,
    NoteForm,
    ParameterCatalog,
    RecordEditDialogs,
    WaterChangeForm,
    image_data_uri,
)

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
    background: linear-gradient(135deg, #10251a, #1c3c2a, #315a3e) fixed !important;
    color: #eaf3eb;
}

.q-layout,
.q-page-container,
.q-page,
.q-tab-panels,
.q-tab-panel {
    background: transparent !important;
}

.q-header {
    background: linear-gradient(110deg, rgba(16, 37, 26, 0.96), rgba(31, 61, 42, 0.94)) !important;
    border-bottom: 1px solid rgba(150, 205, 149, 0.22);
    backdrop-filter: blur(12px);
}

.q-card,
.q-menu,
.q-dialog__inner > .q-card {
    background: rgba(14, 32, 22, 0.9) !important;
    border: 1px solid rgba(150, 205, 149, 0.18);
    border-radius: 18px;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.18);
}

.q-tab {
    color: #b9cbb9;
}

.q-tab--active {
    color: #9cdda0 !important;
}

.q-tab__indicator {
    background: #57a66a !important;
}

.q-field--outlined .q-field__control:before {
    border-color: rgba(168, 196, 168, 0.38);
}

.q-field--focused .q-field__control:after {
    border-color: #57a66a;
}

.q-field__native,
.q-field__input,
.q-field__label {
    color: #eaf3eb;
}

.q-field--filled .q-field__control {
    background: rgba(8, 24, 16, 0.4);
    border-radius: 10px 10px 0 0;
}

.q-table__container {
    background: rgba(14, 32, 22, 0.86);
    border: 1px solid rgba(150, 205, 149, 0.16);
    border-radius: 16px;
    color: #eaf3eb;
}

.q-table thead tr {
    background: rgba(70, 115, 77, 0.28);
}

.q-table tbody tr:hover {
    background: rgba(73, 154, 83, 0.12);
}

.q-separator {
    background: rgba(168, 196, 168, 0.2);
}
</style>
"""


def _format_datetime(value: datetime | None, language: str) -> str:
    if value is None:
        return translate(language, "no_measurements")
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


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

    selected_aquarium_id: int | None = None

    def current_aquarium_id() -> int:
        if selected_aquarium_id is None:
            raise ValidationError("Select an aquarium first.")
        return selected_aquarium_id

    ui.colors(
        primary="#347f47",
        secondary="#54785a",
        accent="#83c98b",
        dark="#12271a",
        positive="#65c883",
        negative="#ef8080",
        info="#70b58e",
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
                    measurement_form = MeasurementForm(
                        language,
                        on_save=lambda form: save_measurement(form),
                    )

                    fertilizer_application_form = FertilizerApplicationForm(
                        aquarium_service,
                        current_aquarium_id,
                        language,
                        on_save=lambda form: save_fertilizer_application(form),
                    )

                    NoteForm(
                        language,
                        on_save=lambda form: save_note(form),
                    )

                    WaterChangeForm(
                        language,
                        {
                            source.value: t(translation_key)
                            for source, translation_key in SOURCE_TRANSLATION_KEYS.items()
                        },
                        on_save=lambda form: save_water_change(form),
                    )

                    activity_history = ActivityHistory(
                        record_service,
                        current_aquarium_id,
                        language,
                        {
                            source: t(translation_key)
                            for source, translation_key in SOURCE_TRANSLATION_KEYS.items()
                        },
                        lambda: record_edit_dialogs,
                        _notify_error,
                    )

                    measurement_chart = MeasurementChart(
                        record_service,
                        current_aquarium_id,
                        language,
                    )

            with ui.tab_panel(aquariums_tab):
                with ui.row().classes("items-center"):
                    ui.label(t("tab_aquariums")).classes("text-h6")
                    ui.button(
                        t("add_aquarium"),
                        icon="add",
                        on_click=lambda: aquarium_dialog.open(),
                    )
                aquariums_container = ui.column().classes("w-full")

            with ui.tab_panel(settings_tab):
                with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2 gap-4 w-full"):
                    parameter_catalog = ParameterCatalog(
                        parameter_service,
                        language,
                        measurement_form.set_parameters,
                        on_saved=lambda: refresh_all(),
                        on_error=_notify_error,
                    )

                    fertilizer_catalog = FertilizerCatalog(
                        fertilizer_service,
                        language,
                        fertilizer_application_form.set_fertilizers,
                        on_saved=lambda: refresh_all(),
                        on_error=_notify_error,
                    )

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
        aquarium_dialog.open(aquarium)

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
                            ui.image(image_data_uri(item.aquarium.thumbnail_data)).classes(
                                "w-full h-40 rounded-lg object-cover cursor-pointer"
                            ).on("click", open_aquarium).tooltip(t("open_aquarium"))
                        else:
                            placeholder = ui.column().classes(
                                "w-full h-40 items-center justify-center rounded-lg bg-emerald-950"
                                " cursor-pointer"
                            ).on("click", open_aquarium).tooltip(t("open_aquarium"))
                            with placeholder:
                                ui.icon("image", size="48px").classes("text-emerald-300")
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
                        ui.image(image_data_uri(aquarium.thumbnail_data)).classes(
                            "ml-auto h-32 w-48 shrink-0 rounded-lg object-cover"
                        )
                    else:
                        with ui.column().classes(
                            "ml-auto h-32 w-48 shrink-0 items-center justify-center rounded-lg bg-emerald-950"
                        ):
                            ui.icon("image", size="40px").classes("text-emerald-300")
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
                                on_click=lambda item=aquarium: aquarium_dialog.open(item),
                            ).props("flat")
                            ui.button(
                                t("archive") if aquarium.active else t("restore"),
                                icon="archive" if aquarium.active else "unarchive",
                                on_click=lambda aquarium_id=aquarium.id, active=not aquarium.active: toggle_aquarium(
                                    aquarium_id, active
                                ),
                            )

    def refresh_all() -> None:
        refresh_dashboard()
        refresh_aquariums()
        parameter_catalog.refresh()
        fertilizer_catalog.refresh()
        refresh_aquarium_details()
        activity_history.refresh()
        measurement_chart.refresh()

    record_edit_dialogs = RecordEditDialogs(
        record_service,
        parameter_service,
        fertilizer_service,
        current_aquarium_id,
        language,
        {
            source.value: t(translation_key)
            for source, translation_key in SOURCE_TRANSLATION_KEYS.items()
        },
        on_saved=refresh_all,
        on_error=_notify_error,
    )

    aquarium_dialog = AquariumDialog(
        aquarium_service,
        language,
        on_saved=refresh_all,
        on_error=_notify_error,
    )

    def toggle_aquarium(aquarium_id: int, active: bool) -> None:
        try:
            aquarium_service.set_active(aquarium_id, active)
        except NotFoundError as error:
            _notify_error(error)
            return
        refresh_all()

    def save_measurement(form: MeasurementForm) -> None:
        try:
            values = form.values
            aquarium_id = current_aquarium_id()
            record_service.record_measurement(
                aquarium_id,
                values.timestamp,
                values.parameter_id,
                values.value,
                values.note,
            )
        except (ValidationError, NotFoundError) as error:
            _notify_error(error)
            return
        form.reset_after_save()
        ui.notify(t("saved_measurement"), type="positive")
        refresh_all()

    def save_note(form: NoteForm) -> None:
        try:
            values = form.values
            record_service.add_note(
                current_aquarium_id(),
                values.timestamp,
                values.category,
                values.content,
            )
        except (ValidationError, NotFoundError) as error:
            _notify_error(error)
            return
        form.reset_after_save()
        ui.notify(t("saved_note"), type="positive")
        refresh_all()

    def save_water_change(form: WaterChangeForm) -> None:
        try:
            values = form.values
            record_service.add_water_change(
                current_aquarium_id(),
                values.timestamp,
                values.source,
                values.volume_liters,
                values.description,
            )
        except (ValidationError, NotFoundError) as error:
            _notify_error(error)
            return
        form.reset_after_save()
        ui.notify(t("saved_water_change"), type="positive")
        refresh_all()

    def save_fertilizer_application(form: FertilizerApplicationForm) -> None:
        try:
            values = form.values
            record_service.add_fertilizer_application(
                current_aquarium_id(),
                values.timestamp,
                values.fertilizer_id,
                values.actual_dose_ml,
                values.notes,
            )
        except (ValidationError, NotFoundError) as error:
            _notify_error(error)
            return
        form.reset_after_save()
        ui.notify(t("saved_fertilizer_application"), type="positive")
        refresh_all()

    refresh_all()
