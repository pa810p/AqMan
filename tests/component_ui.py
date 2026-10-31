from __future__ import annotations

from datetime import datetime, timezone


class FakeControl:
    def __init__(
        self,
        label: str = "",
        value=None,
        options=None,
        on_click=None,
        **kwargs,
    ) -> None:
        self.label = label
        self.value = value
        self.options = options or {}
        self.on_click = on_click
        self.visible = True
        self.text = label
        self.source = None
        self.classes_value = ""
        self.props_value = ""
        self.updated = 0
        self.enabled = True
        self.deleted = False
        self.kwargs = kwargs
        self.on_change = None

    def classes(self, value):
        self.classes_value = value
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def props(self, value):
        self.props_value = value
        return self

    def tooltip(self, value):
        self.tooltip_value = value
        return self

    def set_visibility(self, visible):
        self.visible = visible

    def set_source(self, source):
        self.source = source

    def update(self):
        self.updated += 1

    def on_value_change(self, callback):
        self.on_change = callback

    def disable(self):
        self.enabled = False

    def enable(self):
        self.enabled = True

    def delete(self):
        self.deleted = True

    def clear(self):
        self.cleared = True


class FakeDialog(FakeControl):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def open(self):
        self.opened = True

    def close(self):
        self.closed = True


class FakeUI:
    def __init__(self) -> None:
        self.controls: list[FakeControl] = []
        self.dialogs: list[FakeDialog] = []
        self.notifications: list[tuple[str, str | None]] = []

    def _create(self, *args, **kwargs):
        label = kwargs.pop("label", args[0] if args else "")
        control = FakeControl(label=label, **kwargs)
        self.controls.append(control)
        return control

    def card(self):
        return self._create()

    def row(self):
        return self._create()

    def column(self):
        return self._create()

    def dialog(self):
        dialog = FakeDialog()
        self.dialogs.append(dialog)
        return dialog

    def input(self, *args, **kwargs):
        return self._create(*args, **kwargs)

    def number(self, *args, **kwargs):
        return self._create(*args, **kwargs)

    def textarea(self, *args, **kwargs):
        return self._create(*args, **kwargs)

    def select(self, *args, **kwargs):
        if args and "options" not in kwargs:
            kwargs["options"] = args[0]
        return self._create(*args[1:], **kwargs) if args else self._create(**kwargs)

    def label(self, *args, **kwargs):
        return self._create(*args, **kwargs)

    def image(self, *args, **kwargs):
        image = self._create(*args, **kwargs)
        image.source = args[0] if args else ""
        return image

    def button(self, *args, **kwargs):
        return self._create(*args, **kwargs)

    def upload(self, *args, **kwargs):
        return self._create(*args, **kwargs)

    def separator(self, *args, **kwargs):
        return self._create(*args, **kwargs)

    def notify(self, message, type=None):
        self.notifications.append((message, type))

    def by_label(self, label):
        matches = [control for control in self.controls if control.label == label]
        assert matches, f"No UI control found with label {label!r}"
        return matches[-1]

    def buttons(self):
        return [control for control in self.controls if control.on_click is not None]


class FakeDateTimePicker:
    def __init__(self, label, value=None, *, show_time=True) -> None:
        self.label = label
        self.value = value or datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
        self.show_time = show_time

    def set_value(self, value):
        self.value = value


def install_ui(monkeypatch, *modules):
    fake_ui = FakeUI()
    for module in modules:
        monkeypatch.setattr(module, "ui", fake_ui)
    return fake_ui


def install_datetime_picker(monkeypatch, *modules):
    for module in modules:
        monkeypatch.setattr(module, "DateTimePicker", FakeDateTimePicker)


def saved_object(**values):
    return SimpleNamespace(**values)
