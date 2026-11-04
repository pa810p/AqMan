import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import URL

_DEFAULT_CONFIG = """[server]
port = 8080

[ui]
show_time_in_datetime_picker = false
activity_history_page_size = 10
activity_history_range_days = 365
"""


@dataclass(frozen=True)
class Settings:
    data_directory: Path
    config_file: Path
    show_time_in_datetime_picker: bool
    activity_history_page_size: int
    activity_history_range_days: int
    port: int

    @property
    def database_path(self) -> Path:
        return self.data_directory / "aquarium_manager.sqlite3"

    @property
    def database_url(self) -> str:
        return URL.create("sqlite", database=str(self.database_path)).render_as_string(
            hide_password=False
        )


def get_settings() -> Settings:
    configured_directory = os.environ.get("AQMAN_DATA_DIR")
    if configured_directory:
        data_directory = Path(configured_directory).expanduser()
    else:
        xdg_data_home = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        ).expanduser()
        data_directory = xdg_data_home / "aquarium-manager"

    configured_file = os.environ.get("AQMAN_CONFIG_FILE")
    if configured_file:
        config_file = Path(configured_file).expanduser()
    else:
        configured_xdg_home = os.environ.get("XDG_CONFIG_HOME") or (
            Path.home() / ".config"
        )
        xdg_config_home = Path(configured_xdg_home).expanduser()
        config_file = xdg_config_home / "aquarium-manager" / "config.toml"

    (
        show_time_in_datetime_picker,
        activity_history_page_size,
        activity_history_range_days,
        port,
    ) = _load_configuration(config_file)
    return Settings(
        data_directory=data_directory,
        config_file=config_file,
        show_time_in_datetime_picker=show_time_in_datetime_picker,
        activity_history_page_size=activity_history_page_size,
        activity_history_range_days=activity_history_range_days,
        port=port,
    )


def _load_configuration(config_file: Path) -> tuple[bool, int, int, int]:
    try:
        config_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise OSError(
            f"Cannot create the configuration directory {config_file.parent}."
        ) from error

    try:
        with config_file.open("x", encoding="utf-8") as file:
            file.write(_DEFAULT_CONFIG)
    except FileExistsError:
        pass
    except OSError as error:
        raise OSError(f"Cannot create the configuration file {config_file}.") from error

    try:
        with config_file.open("rb") as file:
            config = tomllib.load(file)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"Invalid TOML in configuration file {config_file}.") from error
    except OSError as error:
        raise OSError(f"Cannot read the configuration file {config_file}.") from error

    ui_settings = config.get("ui", {})
    if not isinstance(ui_settings, dict):
        raise ValueError(f"The [ui] section in {config_file} must be a table.")
    server_settings = config.get("server", {})
    if not isinstance(server_settings, dict):
        raise ValueError(f"The [server] section in {config_file} must be a table.")

    show_time = ui_settings.get("show_time_in_datetime_picker", False)
    if not isinstance(show_time, bool):
        raise ValueError(
            f"ui.show_time_in_datetime_picker in {config_file} must be true or false."
        )
    activity_history_page_size = ui_settings.get("activity_history_page_size", 10)
    if (
        isinstance(activity_history_page_size, bool)
        or not isinstance(activity_history_page_size, int)
        or activity_history_page_size < 1
    ):
        raise ValueError(
            f"ui.activity_history_page_size in {config_file} must be a positive integer."
        )
    activity_history_range_days = ui_settings.get("activity_history_range_days", 365)
    if (
        isinstance(activity_history_range_days, bool)
        or not isinstance(activity_history_range_days, int)
        or activity_history_range_days < 1
    ):
        raise ValueError(
            f"ui.activity_history_range_days in {config_file} must be a positive integer."
        )

    port = _validate_port(
        server_settings.get("port", 8080),
        f"server.port in {config_file}",
    )
    environment_port = os.environ.get("AQMAN_PORT")
    if environment_port is not None:
        try:
            port = int(environment_port)
        except ValueError as error:
            raise ValueError("AQMAN_PORT must be an integer between 1 and 65535.") from error
        port = _validate_port(port, "AQMAN_PORT")
    return (
        show_time,
        activity_history_page_size,
        activity_history_range_days,
        port,
    )


def _validate_port(value: object, source: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= 65535
    ):
        raise ValueError(f"{source} must be an integer between 1 and 65535.")
    return value
