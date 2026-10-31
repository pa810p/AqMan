from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

import pytest

from aqman.models import Parameter
from aqman.services import NotFoundError, ParameterService, ValidationError
from aqman.ui.components import parameter_catalog as parameter_catalog_module
from aqman.ui.components.parameter_catalog import ParameterCatalog


class FakeElement:
    def __init__(
        self,
        text: str | None = None,
        icon: str | None = None,
        on_click: Callable[[], Any] | None = None,
    ) -> None:
        self.text = text
        self.icon = icon
        self.on_click = on_click
        self.value: str | None = None
        self.opened = False
        self.closed = False
        self.cleared = False

    def __enter__(self) -> FakeElement:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def classes(self, *_: str) -> FakeElement:
        return self

    def props(self, *_: str) -> FakeElement:
        return self

    def tooltip(self, *_: str) -> FakeElement:
        return self

    def clear(self) -> None:
        self.cleared = True

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True


class FakeUI:
    def __init__(self) -> None:
        self.labels: list[str] = []
        self.buttons: list[FakeElement] = []
        self.inputs: list[FakeElement] = []
        self.textareas: list[FakeElement] = []
        self.columns: list[FakeElement] = []
        self.dialogs: list[FakeElement] = []
        self.notifications: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.separator_count = 0

    def card(self) -> FakeElement:
        return FakeElement()

    def row(self) -> FakeElement:
        return FakeElement()

    def column(self) -> FakeElement:
        element = FakeElement()
        self.columns.append(element)
        return element

    def dialog(self) -> FakeElement:
        element = FakeElement()
        self.dialogs.append(element)
        return element

    def label(self, text: str) -> FakeElement:
        self.labels.append(text)
        return FakeElement(text=text)

    def button(self, *args: str, **kwargs: object) -> FakeElement:
        text = args[0] if args else None
        icon = kwargs.get("icon")
        on_click = kwargs.get("on_click")
        element = FakeElement(
            text=text,
            icon=icon if isinstance(icon, str) else None,
            on_click=on_click if callable(on_click) else None,
        )
        self.buttons.append(element)
        return element

    def input(self, text: str) -> FakeElement:
        element = FakeElement(text=text)
        self.inputs.append(element)
        return element

    def textarea(self, text: str) -> FakeElement:
        element = FakeElement(text=text)
        self.textareas.append(element)
        return element

    def separator(self) -> FakeElement:
        self.separator_count += 1
        return FakeElement()

    def notify(self, *args: object, **kwargs: object) -> None:
        self.notifications.append((args, kwargs))


@pytest.fixture
def catalog_setup(monkeypatch: pytest.MonkeyPatch):
    fake_ui = FakeUI()
    monkeypatch.setattr(parameter_catalog_module, "ui", fake_ui)
    monkeypatch.setattr(
        parameter_catalog_module,
        "translate",
        lambda _language, key: key,
    )
    service = Mock(spec=ParameterService)
    changed_parameters: list[list[Parameter]] = []
    saved_calls: list[bool] = []
    errors: list[Exception] = []
    catalog = ParameterCatalog(
        service,
        "en",
        changed_parameters.append,
        lambda: saved_calls.append(True),
        errors.append,
    )
    return catalog, fake_ui, service, changed_parameters, saved_calls, errors


def _click_button(fake_ui: FakeUI, text: str) -> None:
    button = next(button for button in fake_ui.buttons if button.text == text)
    assert button.on_click is not None
    button.on_click()


def test_refresh_notifies_and_renders_empty_state(catalog_setup) -> None:
    catalog, fake_ui, service, changed, _, _ = catalog_setup
    service.list_parameters.return_value = []

    catalog.refresh()

    assert changed == [[]]
    assert fake_ui.columns[0].cleared
    assert "empty_parameters" in fake_ui.labels


def test_refresh_renders_parameters_and_description(catalog_setup) -> None:
    catalog, fake_ui, service, changed, _, _ = catalog_setup
    parameters = [
        Parameter(id=1, name="NO3", unit="ppm", description="Nitrate"),
        Parameter(id=2, name="K", unit="mg/L", description=None),
    ]
    service.list_parameters.return_value = parameters

    catalog.refresh()

    assert changed == [parameters]
    assert fake_ui.columns[0].cleared
    assert fake_ui.labels.count("NO3") == 1
    assert fake_ui.labels.count("ppm") == 1
    assert "Nitrate" in fake_ui.labels
    assert fake_ui.labels.count("K") == 1
    assert fake_ui.labels.count("mg/L") == 1
    assert fake_ui.separator_count == 2
    delete_buttons = [
        button
        for button in fake_ui.buttons
        if button.icon == "delete" and button.text is None
    ]
    assert len(delete_buttons) == 2


def test_open_dialog_saves_parameter_and_notifies(catalog_setup) -> None:
    catalog, fake_ui, service, _, saved, errors = catalog_setup
    catalog.open_dialog()
    fake_ui.inputs[0].value = "NO3"
    fake_ui.inputs[1].value = "ppm"
    fake_ui.textareas[0].value = "Nitrate"
    service.create_parameter.return_value = Parameter(
        id=1,
        name="NO3",
        unit="ppm",
        description="Nitrate",
    )

    _click_button(fake_ui, "save")

    service.create_parameter.assert_called_once_with("NO3", "ppm", "Nitrate")
    assert fake_ui.dialogs[0].opened
    assert fake_ui.dialogs[0].closed
    assert fake_ui.notifications == [
        (("saved_parameter",), {"type": "positive"}),
    ]
    assert saved == [True]
    assert errors == []


def test_open_dialog_reports_validation_error_and_can_cancel(catalog_setup) -> None:
    catalog, fake_ui, service, _, saved, errors = catalog_setup
    catalog.open_dialog()
    service.create_parameter.side_effect = ValidationError("duplicate parameter")

    _click_button(fake_ui, "save")

    assert len(errors) == 1
    assert isinstance(errors[0], ValidationError)
    assert not fake_ui.dialogs[0].closed
    assert saved == []

    _click_button(fake_ui, "cancel")

    assert fake_ui.dialogs[0].closed


def test_confirm_delete_deletes_and_notifies(catalog_setup) -> None:
    catalog, fake_ui, service, _, saved, errors = catalog_setup
    catalog.confirm_delete(7)

    _click_button(fake_ui, "delete_parameter")

    service.delete_parameter.assert_called_once_with(7)
    assert fake_ui.dialogs[0].opened
    assert fake_ui.dialogs[0].closed
    assert fake_ui.notifications == [
        (("deleted_parameter",), {"type": "positive"}),
    ]
    assert saved == [True]
    assert errors == []


@pytest.mark.parametrize(
    "error",
    [
        NotFoundError("Parameter not found"),
        ValidationError("Parameter is in use"),
    ],
)
def test_confirm_delete_reports_service_errors(
    catalog_setup,
    error: Exception,
) -> None:
    catalog, fake_ui, service, _, saved, errors = catalog_setup
    service.delete_parameter.side_effect = error
    catalog.confirm_delete(7)

    _click_button(fake_ui, "delete_parameter")

    assert fake_ui.dialogs[0].closed
    assert errors == [error]
    assert saved == []
    assert fake_ui.notifications == []


def test_confirm_delete_can_be_cancelled(catalog_setup) -> None:
    catalog, fake_ui, service, _, _, _ = catalog_setup
    catalog.confirm_delete(7)

    _click_button(fake_ui, "cancel")

    assert fake_ui.dialogs[0].closed
    service.delete_parameter.assert_not_called()
