from collections.abc import Callable
from datetime import datetime
from typing import Any

from nicegui import ui

from aqman.models import Measurement, Parameter
from aqman.services import RecordService, ValidationError
from aqman.translations import translate


def _measurement_chart_options(
    parameter: Parameter,
    measurements: list[Measurement],
) -> dict[str, Any]:
    return {
        "animation": False,
        "backgroundColor": "transparent",
        "grid": {"left": 56, "right": 24, "top": 32, "bottom": 48, "containLabel": True},
        "tooltip": {"trigger": "item"},
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
                "type": "scatter",
                "name": parameter.name,
                "data": [
                    [int(measurement.timestamp.timestamp() * 1000), measurement.value]
                    for measurement in measurements
                ],
                "symbol": "circle",
                "symbolSize": 8,
                "itemStyle": {"color": "#7acb84"},
            }
        ],
        "textStyle": {"color": "#eaf3eb"},
    }


class MeasurementChart:
    def __init__(
        self,
        record_service: RecordService,
        language: str,
        on_parameter_changed: Callable[[], None],
    ) -> None:
        self._record_service = record_service
        self._language = language
        self._on_parameter_changed = on_parameter_changed

        with ui.card().classes("w-full col-span-2"):
            ui.label(self._t("measurement_chart")).classes("text-h6")
            with ui.row().classes("w-full items-end gap-4"):
                self._parameter = ui.select(
                    {},
                    label=self._t("parameter"),
                ).classes("min-w-48 flex-1")
            self._status = ui.label().classes("text-body2")
            self._chart = ui.echart({}).classes("w-full h-64")

        self._parameter.on_value_change(lambda _: self._on_parameter_changed())

    def clear(self, *, reset_parameter: bool = False) -> None:
        if reset_parameter:
            self._parameter.options = {}
            self._parameter.value = None
            self._parameter.update()
        self._set_chart_options({})
        self._chart.set_visibility(False)
        self._status.set_visibility(False)

    def refresh(self, aquarium_id: int, start: datetime, end: datetime) -> None:
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

        if parameter_id is None:
            self._set_chart_options({})
            self._chart.set_visibility(False)
            self._status.set_text(self._t("chart_no_parameters"))
            self._status.set_visibility(True)
            return

        try:
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
