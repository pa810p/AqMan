from datetime import datetime
from typing import Any

from nicegui import ui

from aqman.models import FertilizerApplication
from aqman.services import RecordService
from aqman.translations import translate

_SERIES_COLORS = (
    "#7acb84",
    "#70b5e8",
    "#e6bd70",
    "#d98acc",
    "#ef8a72",
    "#a997e8",
    "#6fc9c0",
)


def _fertilizer_application_chart_options(
    applications: list[FertilizerApplication],
    dose_axis_label: str,
) -> dict[str, Any]:
    grouped: dict[int, tuple[str, list[dict[str, Any]]]] = {}
    for application in applications:
        fertilizer = application.fertilizer
        points = grouped.setdefault(
            fertilizer.id,
            (fertilizer.name, []),
        )[1]
        points.append(
            {
                "name": application.timestamp.astimezone().strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "value": [
                    int(application.timestamp.timestamp() * 1000),
                    application.actual_dose_ml,
                ],
            }
        )

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
            "axisLabel": {"formatter": "{yyyy}-{MM}-{dd}"},
            "axisLine": {"lineStyle": {"color": "#9db59f"}},
            "splitLine": {"lineStyle": {"color": "rgba(168, 196, 168, 0.12)"}},
        },
        "yAxis": {
            "type": "value",
            "name": dose_axis_label,
            "scale": True,
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


class FertilizerApplicationChart:
    def __init__(
        self,
        record_service: RecordService,
        language: str,
    ) -> None:
        self._record_service = record_service
        self._language = language

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
