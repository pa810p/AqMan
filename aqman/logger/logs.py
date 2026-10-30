import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOGGER_NAME = "aqman"
DEFAULT_LOG_LEVEL = "DEBUG"
MAX_LOG_FILE_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5
_FORMAT = "%(asctime)s - %(levelname)s - [pid:%(process)d] - %(name)s - %(message)s"


def _to_level(log_level: int | str) -> int:
    if isinstance(log_level, int):
        return log_level
    return getattr(logging, str(log_level).upper(), logging.INFO)


def configure_logging(
    log_level: int | str = DEFAULT_LOG_LEVEL,
    logger_name: str = DEFAULT_LOGGER_NAME,
    log_directory: Path | None = None,
) -> logging.Logger:
    level = _to_level(log_level)
    log_path = (log_directory or Path("logs")) / f"{DEFAULT_LOGGER_NAME}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    resolved_log_path = log_path.resolve()
    for handler in root_logger.handlers:
        if (
            isinstance(handler, RotatingFileHandler)
            and Path(handler.baseFilename) == resolved_log_path
        ):
            handler.setLevel(level)
            return logging.getLogger(logger_name)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_LOG_FILE_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.set_name("aqman_file")
    file_handler.setFormatter(logging.Formatter(fmt=_FORMAT))
    file_handler.setLevel(level)
    root_logger.addHandler(file_handler)
    return logging.getLogger(logger_name)


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or DEFAULT_LOGGER_NAME)
