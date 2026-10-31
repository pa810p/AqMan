from collections.abc import Callable
from datetime import date, datetime, time, timezone

from nicegui import ui
from nicegui.element import Element
from nicegui.events import ScrollEventArguments

from aqman.services import ValidationError

TIME_WHEEL_ROW_HEIGHT_PX = 32
TIME_WHEEL_VISIBLE_ROWS = 8
TIME_WHEEL_PADDING_ROWS = TIME_WHEEL_VISIBLE_ROWS // 2
TIME_WHEEL_OPEN_DELAY_SECONDS = 0.2
TIME_WHEEL_SCROLL_SETTLE_SECONDS = 0.2


def _local_datetime_parts(value: datetime | None = None) -> tuple[str, str]:
    local_value = value.astimezone() if value is not None else datetime.now().astimezone()
    return local_value.strftime("%Y-%m-%d"), local_value.strftime("%H:%M")


def _local_datetime_input_value(
    value: datetime | None = None,
    *,
    show_time: bool = True,
) -> str:
    date_value, time_value = _local_datetime_parts(value)
    return f"{date_value} {time_value}" if show_time else date_value


def _parse_local_datetime_value(
    value: str | None,
    *,
    show_time: bool = True,
) -> datetime:
    if not value:
        raise ValidationError("Enter a date and time." if show_time else "Enter a date.")
    try:
        if show_time:
            if not ("T" in value or " " in value):
                raise ValidationError("Enter a date and time.")
            parsed = datetime.fromisoformat(value)
        else:
            parsed = datetime.combine(date.fromisoformat(value), time.min)
    except ValueError as error:
        message = "Enter a valid date and time." if show_time else "Enter a valid date."
        raise ValidationError(message) from error
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.astimezone(timezone.utc)


class DateTimePicker:
    def __init__(
        self,
        label: str,
        value: datetime | None = None,
        on_change: Callable[[], None] | None = None,
        show_time: bool = True,
    ) -> None:
        self._on_change = on_change
        self._show_time = show_time
        initial_date, initial_time = _local_datetime_parts(value)
        hour = int(initial_time[:2])
        minute = int(initial_time[3:])
        self._time_parts = {"hour": hour, "minute": minute}
        self.element = ui.input(
            label,
            value=_local_datetime_input_value(value, show_time=show_time),
        ).props("readonly").classes("min-w-64")

        def update_time_part(part: str, selected_value: int) -> None:
            self._time_parts[part] = selected_value
            self._sync_input()

        with self.element.add_slot("append"):
            with ui.menu().props("no-parent-event") as self._menu:
                with ui.row().classes("no-wrap items-start"):
                    self._date_picker = ui.date(initial_date, mask="YYYY-MM-DD")
                    time_controls_classes = "items-center gap-0"
                    if not show_time:
                        time_controls_classes += " hidden"
                    with ui.column().classes(time_controls_classes):
                        ui.label("HH").classes("text-caption")
                        (
                            self._set_hour,
                            self._suspend_hour_scroll,
                            self._center_hour,
                        ) = self._create_numeric_wheel(
                            24,
                            hour,
                            lambda selected_value: update_time_part("hour", selected_value),
                        )
                    with ui.column().classes(time_controls_classes):
                        ui.label("MM").classes("text-caption")
                        (
                            self._set_minute,
                            self._suspend_minute_scroll,
                            self._center_minute,
                        ) = self._create_numeric_wheel(
                            60,
                            minute,
                            lambda selected_value: update_time_part("minute", selected_value),
                        )
            ui.icon("event").classes("cursor-pointer").on(
                "click",
                self._open_menu,
            )

        self.element.on("click", self._open_menu)
        self._date_picker.on_value_change(self._handle_date_change)

    @property
    def value(self) -> datetime:
        return _parse_local_datetime_value(
            self.element.value,
            show_time=self._show_time,
        )

    def set_value(self, value: datetime) -> None:
        date_value, time_value = _local_datetime_parts(value)
        self._date_picker.value = date_value
        self._date_picker.update()
        self._time_parts["hour"] = int(time_value[:2])
        self._time_parts["minute"] = int(time_value[3:])
        self._set_hour(self._time_parts["hour"])
        self._set_minute(self._time_parts["minute"])
        self.element.value = _local_datetime_input_value(
            value,
            show_time=self._show_time,
        )
        self.element.update()

    def _create_numeric_wheel(
        self,
        number_of_values: int,
        initial_value: int,
        on_select: Callable[[int], None],
    ) -> tuple[Callable[[int], None], Callable[[], None], Callable[[], None]]:
        selected_value = initial_value
        number_labels: list[Element] = []
        wheel_height = TIME_WHEEL_ROW_HEIGHT_PX * TIME_WHEEL_VISIBLE_ROWS
        wheel_ready = False

        def scroll_position(value: int) -> float:
            return max(
                0,
                (TIME_WHEEL_PADDING_ROWS + value) * TIME_WHEEL_ROW_HEIGHT_PX
                - (wheel_height - TIME_WHEEL_ROW_HEIGHT_PX) / 2,
            )

        def set_selected_value(value: int, notify: bool = True) -> None:
            nonlocal selected_value
            if not 0 <= value < number_of_values:
                return
            changed = value != selected_value
            if changed:
                selected_value = value
                for index, number_label in enumerate(number_labels):
                    if index == selected_value:
                        number_label.classes(add="bg-primary text-white")
                    else:
                        number_label.classes(remove="bg-primary text-white")
            if wheel_ready:
                wheel.scroll_to(pixels=scroll_position(selected_value))
            if notify and changed:
                on_select(selected_value)

        def handle_scroll(event: ScrollEventArguments) -> None:
            if not wheel_ready:
                return
            centered_index = round(
                (
                    event.vertical_position
                    + (wheel_height - TIME_WHEEL_ROW_HEIGHT_PX) / 2
                )
                / TIME_WHEEL_ROW_HEIGHT_PX
            ) - TIME_WHEEL_PADDING_ROWS
            set_selected_value(
                min(max(centered_index, 0), number_of_values - 1)
            )

        def enable_wheel() -> None:
            nonlocal wheel_ready
            wheel_ready = True

        wheel = ui.scroll_area(on_scroll=handle_scroll).style(
            f"height: {wheel_height}px; width: 3.5rem;"
        )
        with wheel:
            with ui.column().classes("w-full items-center gap-0"):
                for _ in range(TIME_WHEEL_PADDING_ROWS):
                    ui.element("div").classes("w-full shrink-0").style(
                        f"height: {TIME_WHEEL_ROW_HEIGHT_PX}px;"
                    )
                for value in range(number_of_values):
                    number_label = ui.label(f"{value:02d}").classes(
                        "w-full cursor-pointer select-none rounded text-center"
                    ).style(
                        f"height: {TIME_WHEEL_ROW_HEIGHT_PX}px; "
                        f"line-height: {TIME_WHEEL_ROW_HEIGHT_PX}px;"
                    )
                    if value == selected_value:
                        number_label.classes("bg-primary text-white")
                    number_label.on(
                        "click",
                        lambda value=value: set_selected_value(value),
                    )
                    number_labels.append(number_label)
                for _ in range(TIME_WHEEL_PADDING_ROWS):
                    ui.element("div").classes("w-full shrink-0").style(
                        f"height: {TIME_WHEEL_ROW_HEIGHT_PX}px;"
                    )

        def set_value(value: int) -> None:
            set_selected_value(value, notify=False)

        def center_selected_value() -> None:
            nonlocal wheel_ready
            wheel_ready = False
            wheel.scroll_to(pixels=scroll_position(selected_value))
            ui.timer(
                TIME_WHEEL_SCROLL_SETTLE_SECONDS,
                enable_wheel,
                once=True,
                immediate=False,
            )

        def suspend_scroll_events() -> None:
            nonlocal wheel_ready
            wheel_ready = False

        return set_value, suspend_scroll_events, center_selected_value

    def _handle_date_change(self, _: object) -> None:
        self._sync_input()

    def _sync_input(self) -> None:
        if self._date_picker.value is None:
            return
        self.element.value = (
            f"{self._date_picker.value} "
            f"{self._time_parts['hour']:02d}:{self._time_parts['minute']:02d}"
            if self._show_time
            else str(self._date_picker.value)
        )
        self.element.update()
        if self._on_change is not None:
            self._on_change()

    def _center_time_wheels(self) -> None:
        self._center_hour()
        self._center_minute()

    def _open_menu(self) -> None:
        if self._show_time:
            self._suspend_hour_scroll()
            self._suspend_minute_scroll()
        self._menu.open()
        if not self._show_time:
            return
        ui.timer(
            TIME_WHEEL_OPEN_DELAY_SECONDS,
            self._center_time_wheels,
            once=True,
            immediate=False,
        )
