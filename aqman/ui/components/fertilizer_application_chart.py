from collections import defaultdict
from datetime import date, datetime
from typing import Any

from nicegui import ui

from aqman.models import FertilizerApplication
from aqman.services import RecordService
from aqman.translations import translate
from aqman.ui.components.chart_axis import (
    format_tooltip_datetime,
    x_axis_date_format,
)

_SERIES_COLORS = (
    "#7acb84",
    "#70b5e8",
    "#e6bd70",
    "#d98acc",
    "#ef8a72",
    "#a997e8",
    "#6fc9c0",
)
_STACKED_POINT_OFFSET_PX = 4


def _fertilizer_application_chart_options(
    applications: list[FertilizerApplication],
    dose_axis_label: str,
    start: datetime,
    end: datetime,
    show_time: bool = True,
) -> dict[str, Any]:
    symbol_offsets = _same_day_same_dose_offsets(applications)
    grouped: dict[int, tuple[str, list[dict[str, Any]]]] = {}
    for application_index, application in enumerate(applications):
        fertilizer = application.fertilizer
        points = grouped.setdefault(
            fertilizer.id,
            (fertilizer.name, []),
        )[1]
        point: dict[str, Any] = {
            "name": format_tooltip_datetime(application.timestamp, show_time),
            "value": [
                int(application.timestamp.timestamp() * 1000),
                application.actual_dose_ml,
            ],
        }
        if symbol_offsets[application_index]:
            point["symbolOffset"] = [symbol_offsets[application_index], 0]
        points.append(point)

    ordered_groups = sorted(
        grouped.values(),
        key=lambda item: item[0].casefold(),
    )
    return {
        "animation": False,
        "backgroundColor": "transparent",
        "color": list(_SERIES_COLORS),
        "grid": {"left": 56, "right": 24, "top": 56, "bottom": 48, "containLabel": True},
        "legend": {
            "type": "scroll",
            "textStyle": {"color": "#eaf3eb"},
        },
        "tooltip": {"trigger": "item"},
        "xAxis": {
            "type": "time",
            "min": int(start.timestamp() * 1000),
            "max": int(end.timestamp() * 1000),
            "axisLabel": {
                "formatter": x_axis_date_format(start, end),
                "hideOverlap": True,
            },
            "axisLine": {"lineStyle": {"color": "#9db59f"}},
            "splitLine": {"lineStyle": {"color": "rgba(168, 196, 168, 0.12)"}},
        },
        "yAxis": {
            "type": "value",
            "name": dose_axis_label,
            "min": 0,
            "max": "dataMax",
            "axisLine": {"lineStyle": {"color": "#9db59f"}},
            "splitLine": {"lineStyle": {"color": "rgba(168, 196, 168, 0.2)"}},
        },
        "series": [
            {
                "type": "scatter",
                "name": name,
                "data": points,
                "symbol": "circle",
                "symbolSize": 10,
                "itemStyle": {"color": _SERIES_COLORS[index % len(_SERIES_COLORS)]},
            }
            for index, (name, points) in enumerate(ordered_groups)
        ],
        "textStyle": {"color": "#eaf3eb"},
    }


def _same_day_same_dose_offsets(
    applications: list[FertilizerApplication],
) -> list[int]:
    applications_by_day_and_dose: dict[
        tuple[date, float], list[int]
    ] = defaultdict(list)
    for index, application in enumerate(applications):
        key = (application.timestamp.astimezone().date(), application.actual_dose_ml)
        applications_by_day_and_dose[key].append(index)

    offsets = [0] * len(applications)
    for indexes in applications_by_day_and_dose.values():
        if len(indexes) < 2:
            continue
        ordered_indexes = sorted(
            indexes,
            key=lambda index: (
                applications[index].timestamp,
                applications[index].id or 0,
                index,
            ),
        )
        for stack_position, index in enumerate(ordered_indexes):
            offsets[index] = stack_position * _STACKED_POINT_OFFSET_PX
    return offsets


class FertilizerApplicationChart:
    def __init__(
        self,
        record_service: RecordService,
        language: str,
        show_time: bool = True,
    ) -> None:
        self._record_service = record_service
        self._language = language
        self._show_time = show_time

        with ui.card().classes("w-full"):
            ui.label(self._t("fertilizer_application_chart")).classes("text-h6")
            self._status = ui.label().classes("text-body2")
            self._chart = ui.echart({}).classes("w-full h-64")

    def clear(self) -> None:
        self._set_chart_options({})
        self._chart.set_visibility(False)
        self._status.set_visibility(False)

    def refresh(
        self,
        aquarium_id: int,
        start: datetime,
        end: datetime,
    ) -> None:
        applications = self._record_service.fertilizer_applications_in_range(
            aquarium_id,
            start,
            end,
        )
        self._set_chart_options(
            _fertilizer_application_chart_options(
                applications,
                self._t("chart_fertilizer_dose"),
                start,
                end,
                show_time=self._show_time,
            )
        )
        self._chart.set_visibility(True)
        self._status.set_text(
            self._t("chart_no_fertilizer_applications") if not applications else ""
        )
        self._status.set_visibility(not applications)

    def _set_chart_options(self, options: dict[str, Any]) -> None:
        self._chart.options.clear()
        self._chart.options.update(options)
        self._chart.update()

    def _t(self, key: str) -> str:
        return translate(self._language, key)
