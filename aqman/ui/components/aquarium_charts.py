import calendar
from collections.abc import Callable
from datetime import datetime, time, timezone

from nicegui import ui

from aqman.services import RecordService, ValidationError
from aqman.translations import translate
from aqman.ui.components.date_time_picker import DateTimePicker
from aqman.ui.components.fertilizer_application_chart import (
    FertilizerApplicationChart,
)
from aqman.ui.components.measurement_chart import MeasurementChart


def _calendar_month_before(value: datetime) -> datetime:
    target_month = value.month - 1
    target_year = value.year
    if target_month == 0:
        target_month = 12
        target_year -= 1
    target_day = min(value.day, calendar.monthrange(target_year, target_month)[1])
    return value.replace(year=target_year, month=target_month, day=target_day)


def _default_chart_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    local_now = (now or datetime.now().astimezone()).astimezone()
    end = local_now.replace(second=0, microsecond=0)
    start = _calendar_month_before(end.replace(tzinfo=None))
    return start, end


def _end_of_local_day(value: datetime) -> datetime:
    local_date = value.astimezone().date()
    local_end = datetime.combine(local_date, time.max).astimezone()
    return local_end.astimezone(timezone.utc)


class AquariumCharts:
    def __init__(
        self,
        record_service: RecordService,
        aquarium_id_provider: Callable[[], int],
        language: str,
        show_time: bool = True,
    ) -> None:
        self._record_service = record_service
        self._aquarium_id_provider = aquarium_id_provider
        self._language = language
        self._show_time = show_time

        with ui.column().classes("w-full col-span-2 gap-4"):
            with ui.card().classes("w-full"):
                ui.label(self._t("chart_date_range")).classes("text-h6")
                with ui.row().classes("w-full items-end gap-4"):
                    self._start = DateTimePicker(
                        self._t("chart_start"),
                        on_change=self.refresh,
                        show_time=show_time,
                    )
                    self._start.element.classes("flex-1")
                    self._end = DateTimePicker(
                        self._t("chart_end"),
                        on_change=self.refresh,
                        show_time=show_time,
                    )
                    self._end.element.classes("flex-1")
                self._range_status = ui.label().classes("text-body2")
                self._range_status.set_visibility(False)

            self._measurement_chart = MeasurementChart(
                record_service,
                language,
                self.refresh_measurement_chart,
            )
            self._fertilizer_chart = FertilizerApplicationChart(
                record_service,
                language,
            )

        start, end = _default_chart_range()
        self._start.set_value(start)
        self._end.set_value(end)

    def refresh(self) -> None:
        try:
            aquarium_id = self._aquarium_id_provider()
        except ValidationError:
            self._clear_charts(reset_parameter=True)
            self._show_range_status("chart_choose_aquarium")
            return

        try:
            start, end = self._chart_range()
        except ValidationError:
            self._clear_charts()
            self._show_range_status("chart_invalid_datetime")
            return
        if start > end:
            self._clear_charts()
            self._show_range_status("chart_invalid_range")
            return

        self._range_status.set_visibility(False)
        self._measurement_chart.refresh(aquarium_id, start, end)
        self._fertilizer_chart.refresh(aquarium_id, start, end)

    def refresh_measurement_chart(self) -> None:
        try:
            aquarium_id = self._aquarium_id_provider()
        except ValidationError:
            self._measurement_chart.clear(reset_parameter=True)
            self._show_range_status("chart_choose_aquarium")
            return

        try:
            start, end = self._chart_range()
        except ValidationError:
            self._measurement_chart.clear()
            self._show_range_status("chart_invalid_datetime")
            return
        if start > end:
            self._measurement_chart.clear()
            self._show_range_status("chart_invalid_range")
            return

        self._range_status.set_visibility(False)
        self._measurement_chart.refresh(aquarium_id, start, end)

    def _chart_range(self) -> tuple[datetime, datetime]:
        start = self._start.value
        end = self._end.value
        if not self._show_time:
            end = _end_of_local_day(end)
        return start, end

    def _clear_charts(self, *, reset_parameter: bool = False) -> None:
        self._measurement_chart.clear(reset_parameter=reset_parameter)
        self._fertilizer_chart.clear()

    def _show_range_status(self, key: str) -> None:
        self._range_status.set_text(self._t(key))
        self._range_status.set_visibility(True)

    def _t(self, key: str) -> str:
        return translate(self._language, key)
