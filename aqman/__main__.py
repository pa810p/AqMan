import argparse
import ctypes.util
import importlib.util
import os
import sys
from pathlib import Path

from nicegui import ui

from aqman.config import get_settings
from aqman.database import create_database_engine, create_session_factory
from aqman.logger import configure_logging
from aqman.migrations import upgrade_database
from aqman.services import AquariumService, FertilizerService, ParameterService, RecordService
from aqman.translations import LANGUAGE_NAMES
from aqman.ui import build_ui


def _validate_native_dependencies() -> None:
    if importlib.util.find_spec("webview") is None:
        raise SystemExit(
            "Standalone mode requires pywebview. Install it with: "
            "python -m pip install -e '.[desktop]'"
        )
    if sys.platform.startswith("linux"):
        missing: list[str] = []
        if importlib.util.find_spec("gi") is None:
            missing.append("Python module gi (PyGObject)")
        if ctypes.util.find_library("gtk-3") is None:
            missing.append("GTK 3")
        if not any(
            ctypes.util.find_library(name) is not None
            for name in ("webkit2gtk-4.1", "webkit2gtk-4.0")
        ):
            missing.append("WebKitGTK 4.0 or 4.1")
        if missing:
            details = ", ".join(missing)
            raise SystemExit(f"Standalone mode cannot start; missing: {details}.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Aquarium Manager.")
    parser.add_argument("--mode", choices=("browser", "native"), default="browser")
    parser.add_argument("--host", default=os.environ.get("AQMAN_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AQMAN_PORT", "8080")))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.mode == "native":
        _validate_native_dependencies()

    settings = get_settings()
    settings.data_directory.mkdir(parents=True, exist_ok=True)
    logger = configure_logging(
        log_level="DEBUG",
        logger_name="aqman",
        log_directory=settings.data_directory / "logs",
    )
    logger.info(
        "Starting Aquarium Manager mode=%s host=%s port=%s",
        args.mode,
        args.host,
        args.port,
    )
    project_root = Path(__file__).resolve().parents[1]
    upgrade_database(settings.database_url, project_root)
    logger.info("Database migrations are up to date.")

    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    aquarium_service = AquariumService(session_factory)
    parameter_service = ParameterService(session_factory)
    fertilizer_service = FertilizerService(session_factory)
    record_service = RecordService(session_factory)

    @ui.page("/")
    def main_page() -> None:
        requested_language = ui.context.client.request.query_params.get("lang", "en")
        language = requested_language if requested_language in LANGUAGE_NAMES else "en"
        build_ui(
            aquarium_service,
            parameter_service,
            fertilizer_service,
            record_service,
            language=language,
            show_time_in_datetime_picker=settings.show_time_in_datetime_picker,
        )

    logger.info("Starting NiceGUI server.")
    ui.run(
        native=args.mode == "native",
        host=args.host,
        port=args.port,
        title="Aquarium Manager",
        window_size=(1280, 800),
        reload=False,
        show=args.mode == "browser",
    )


if __name__ == "__main__":
    main()
