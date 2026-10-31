import calendar
from collections.abc import Callable
from datetime import datetime
from typing import Any

from nicegui import ui

from aqman.models import Measurement, Parameter
from aqman.services import RecordService, ValidationError
from aqman.translations import translate
from aqman.ui.components.date_time_picker import DateTimePicker


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


def _measurement_chart_options(
    parameter: Parameter,
    measurements: list[Measurement],
) -> dict[str, Any]:
    return {
        "animation": False,
        "backgroundColor": "transparent",
        "grid": {"left": 56, "right": 24, "top": 32, "bottom": 48, "containLabel": True},
        "tooltip": {"trigger": "axis"},
        "xAxis": {
            "type": "time",
            "axisLabel": {"formatter": "{yyyy}-{MM}-{dd}"},
            "axisLine": {"lineStyle": {"color": "#9db59f"}},
            "splitLine": {"lineStyle": {"color": "rgba(168, 196, 168, 0.12)"}},
        },
        "yAxis": {
            "type": "value",
            "name": f"{parameter.name} ({parameter.unit})",
            "scale": True,
            "axisLine": {"lineStyle": {"color": "#9db59f"}},
            "splitLine": {"lineStyle": {"color": "rgba(168, 196, 168, 0.2)"}},
        },
        "series": [
            {
                "type": "line",
                "name": parameter.name,
                "data": [
                    [int(measurement.timestamp.timestamp() * 1000), measurement.value]
                    for measurement in measurements
                ],
                "showSymbol": True,
                "symbol": "circle",
                "symbolSize": 8,
                "connectNulls": False,
                "lineStyle": {"color": "#7acb84", "width": 2},
                "itemStyle": {"color": "#7acb84"},
            }
        ],
        "textStyle": {"color": "#eaf3eb"},
    }


class MeasurementChart:
    def __init__(
        self,
        record_service: RecordService,
        aquarium_id_provider: Callable[[], int],
        language: str,
    ) -> None:
        self._record_service = record_service
        self._aquarium_id_provider = aquarium_id_provider
        self._language = language
        self._chart_range_initialized = False

        with ui.card().classes("w-full col-span-2"):
            ui.label(self._t("measurement_chart")).classes("text-h6")
            with ui.row().classes("w-full items-end gap-4"):
                self._parameter = ui.select(
                    {},
                    label=self._t("parameter"),
                ).classes("min-w-48 flex-1")
                self._start = DateTimePicker(
                    self._t("chart_start"),
                    on_change=self.refresh,
                )
                self._start.element.classes("flex-1")
                self._end = DateTimePicker(
                    self._t("chart_end"),
                    on_change=self.refresh,
                )
                self._end.element.classes("flex-1")
            self._status = ui.label().classes("text-body2")
            self._chart = ui.echart({}).classes("w-full h-96")

        self._parameter.on_value_change(lambda _: self.refresh())

    def refresh(self) -> None:
        try:
            aquarium_id = self._aquarium_id_provider()
        except ValidationError:
            self._parameter.options = {}
            self._parameter.value = None
            self._parameter.update()
            self._set_chart_options({})
            self._chart.set_visibility(False)
            self._status.set_text(self._t("chart_choose_aquarium"))
            self._status.set_visibility(True)
            return

        parameters = self._record_service.measured_parameters(aquarium_id)
        parameter_options = {
            parameter.id: f"{parameter.name} ({parameter.unit})"
            for parameter in parameters
        }
        try:
            previous_parameter_id = int(self._parameter.value)
        except (TypeError, ValueError):
            previous_parameter_id = None
        parameter_id = (
            previous_parameter_id
            if previous_parameter_id in parameter_options
            else next(iter(parameter_options), None)
        )
        self._parameter.options = parameter_options
        self._parameter.value = parameter_id
        self._parameter.update()

        if not parameters:
            self._set_chart_options({})
            self._chart.set_visibility(False)
            self._status.set_text(self._t("chart_no_parameters"))
            self._status.set_visibility(True)
            return

        if not self._chart_range_initialized:
            start, end = _default_chart_range()
            self._start.set_value(start)
            self._end.set_value(end)
            self._chart_range_initialized = True

        if parameter_id is None:
            self._set_chart_options({})
            self._chart.set_visibility(False)
            self._status.set_text(self._t("chart_no_parameters"))
            self._status.set_visibility(True)
            return

        try:
            start = self._start.value
            end = self._end.value
            if start > end:
                self._set_chart_options({})
                self._chart.set_visibility(False)
                self._status.set_text(self._t("chart_invalid_range"))
                self._status.set_visibility(True)
                return
            measurements = self._record_service.measurements_in_range(
                aquarium_id,
                parameter_id,
                start,
                end,
            )
        except ValidationError:
            self._set_chart_options({})
            self._chart.set_visibility(False)
            self._status.set_text(self._t("chart_invalid_datetime"))
            self._status.set_visibility(True)
            return

        parameter = next(
            item for item in parameters if item.id == parameter_id
        )
        self._set_chart_options(_measurement_chart_options(parameter, measurements))
        self._chart.set_visibility(True)
        self._status.set_text(self._t("chart_no_data") if not measurements else "")
        self._status.set_visibility(not measurements)

    def _set_chart_options(self, options: dict[str, Any]) -> None:
        self._chart.options.clear()
        self._chart.options.update(options)
        self._chart.update()

    def _t(self, key: str) -> str:
        return translate(self._language, key)
