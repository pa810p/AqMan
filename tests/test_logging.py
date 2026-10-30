import logging

import aqman.ui as ui_module
from aqman.logger import configure_logging
from aqman.services import ValidationError
from aqman.ui import _notify_error


def test_configure_logging_writes_to_rotating_file(tmp_path) -> None:
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    log_path = tmp_path / "aqman.log"

    try:
        logger = configure_logging(
            log_level="DEBUG",
            logger_name="aqman.test",
            log_directory=tmp_path,
        )
        logger.info("Logging setup test.")
        for handler in root_logger.handlers:
            handler.flush()

        assert log_path.exists()
        contents = log_path.read_text(encoding="utf-8")
        assert "INFO" in contents
        assert "aqman.test" in contents
        assert "Logging setup test." in contents
    finally:
        for handler in list(root_logger.handlers):
            if handler not in original_handlers:
                root_logger.removeHandler(handler)
                handler.close()
        root_logger.setLevel(original_level)


def test_handled_errors_are_logged_and_shown_in_english(caplog, monkeypatch) -> None:
    notifications: list[tuple[str, str]] = []

    def fake_notify(message: str, *, type: str) -> None:
        notifications.append((message, type))

    monkeypatch.setattr(ui_module.ui, "notify", fake_notify)
    caplog.set_level(logging.WARNING, logger="aqman.ui")

    _notify_error(ValidationError("Aquarium name is required."))

    assert "Handled ValidationError: Aquarium name is required." in caplog.text
    assert notifications == [("Aquarium name is required.", "negative")]
