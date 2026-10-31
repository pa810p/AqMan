import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from aqman import __main__ as app


def test_parse_args_uses_environment_defaults_and_cli_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AQMAN_HOST", "0.0.0.0")
    monkeypatch.setattr(sys, "argv", ["aqman"])

    defaults = app._parse_args()

    assert (defaults.mode, defaults.host, defaults.port) == ("browser", "0.0.0.0", None)

    monkeypatch.setattr(
        sys,
        "argv",
        ["aqman", "--mode", "native", "--host", "localhost", "--port", "9123"],
    )
    overrides = app._parse_args()

    assert (overrides.mode, overrides.host, overrides.port) == (
        "native",
        "localhost",
        9123,
    )


@pytest.mark.parametrize("port", [0, 65536])
def test_parse_args_rejects_ports_outside_tcp_range(
    monkeypatch: pytest.MonkeyPatch,
    port: int,
) -> None:
    monkeypatch.setattr(sys, "argv", ["aqman", "--port", str(port)])

    with pytest.raises(SystemExit):
        app._parse_args()


def test_native_dependency_validation_reports_missing_linux_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app.sys, "platform", "linux")
    monkeypatch.setattr(app.importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(app.ctypes.util, "find_library", lambda _name: None)

    with pytest.raises(SystemExit, match="pywebview"):
        app._validate_native_dependencies()


def test_native_dependency_validation_reports_missing_webkit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app.sys, "platform", "linux")
    monkeypatch.setattr(
        app.importlib.util,
        "find_spec",
        lambda name: object() if name == "webview" else None,
    )
    monkeypatch.setattr(
        app.ctypes.util,
        "find_library",
        lambda name: "available" if name == "gtk-3" else None,
    )

    with pytest.raises(SystemExit, match="Python module gi.*WebKitGTK"):
        app._validate_native_dependencies()


def test_native_dependency_validation_reports_missing_gtk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app.sys, "platform", "linux")
    monkeypatch.setattr(app.importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(
        app.ctypes.util,
        "find_library",
        lambda name: None if name == "gtk-3" else "available",
    )

    with pytest.raises(SystemExit, match="GTK 3"):
        app._validate_native_dependencies()


def test_native_dependency_validation_succeeds_when_dependencies_are_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app.sys, "platform", "linux")
    monkeypatch.setattr(app.importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(app.ctypes.util, "find_library", lambda _name: "available")

    app._validate_native_dependencies()


@pytest.mark.parametrize(
    ("mode", "expected_native", "expected_show"),
    [("browser", False, True), ("native", True, False)],
)
def test_main_wires_services_page_language_and_server_options(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected_native: bool,
    expected_show: bool,
) -> None:
    log_directory = Path("controlled-data") / "logs"
    settings = SimpleNamespace(
        data_directory=Path("controlled-data"),
        database_url="sqlite:///controlled.sqlite3",
        port=8001,
        show_time_in_datetime_picker=False,
    )
    monkeypatch.setattr(app.Path, "mkdir", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        app,
        "_parse_args",
        lambda: SimpleNamespace(mode=mode, host="127.0.0.2", port=None),
    )
    monkeypatch.setattr(app, "_validate_native_dependencies", Mock())
    monkeypatch.setattr(app, "get_settings", lambda: settings)
    logger = Mock()
    configure_logging = Mock(return_value=logger)
    monkeypatch.setattr(app, "configure_logging", configure_logging)
    monkeypatch.setattr(app, "upgrade_database", Mock())
    engine = object()
    session_factory = object()
    monkeypatch.setattr(app, "create_database_engine", Mock(return_value=engine))
    monkeypatch.setattr(
        app, "create_session_factory", Mock(return_value=session_factory)
    )
    services = {
        "aquarium": Mock(name="aquarium_service"),
        "parameter": Mock(name="parameter_service"),
        "fertilizer": Mock(name="fertilizer_service"),
        "record": Mock(name="record_service"),
    }
    service_constructors = {
        "AquariumService": Mock(return_value=services["aquarium"]),
        "ParameterService": Mock(return_value=services["parameter"]),
        "FertilizerService": Mock(return_value=services["fertilizer"]),
        "RecordService": Mock(return_value=services["record"]),
    }
    for name, constructor in service_constructors.items():
        monkeypatch.setattr(app, name, constructor)
    build_ui = Mock()
    monkeypatch.setattr(app, "build_ui", build_ui)

    registered_pages: list[object] = []
    query_params = {"lang": "pl"}
    run = Mock()
    fake_ui = SimpleNamespace(
        context=SimpleNamespace(
            client=SimpleNamespace(
                request=SimpleNamespace(query_params=query_params),
            )
        ),
        page=lambda path: (
            lambda callback: registered_pages.append((path, callback))
        ),
        run=run,
    )
    monkeypatch.setattr(app, "ui", fake_ui)

    app.main()

    if expected_native:
        app._validate_native_dependencies.assert_called_once_with()
    else:
        app._validate_native_dependencies.assert_not_called()
    configure_logging.assert_called_once_with(
        log_level="DEBUG",
        logger_name="aqman",
        log_directory=log_directory,
    )
    app.upgrade_database.assert_called_once()
    app.create_database_engine.assert_called_once_with(settings.database_url)
    app.create_session_factory.assert_called_once_with(engine)
    for constructor in service_constructors.values():
        constructor.assert_called_once_with(session_factory)
    assert len(registered_pages) == 1
    page_path, page_callback = registered_pages[0]
    assert page_path == "/"

    page_callback()

    build_ui.assert_called_once_with(
        services["aquarium"],
        services["parameter"],
        services["fertilizer"],
        services["record"],
        language="pl",
        show_time_in_datetime_picker=False,
    )
    run.assert_called_once_with(
        native=expected_native,
        host="127.0.0.2",
        port=8001,
        title="Aquarium Manager",
        window_size=(1280, 800),
        reload=False,
        show=expected_show,
    )
