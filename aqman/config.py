import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import URL

_DEFAULT_CONFIG = """[ui]
show_time_in_datetime_picker = false
"""


@dataclass(frozen=True)
class Settings:
    data_directory: Path
    config_file: Path
    show_time_in_datetime_picker: bool

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

    show_time_in_datetime_picker = _load_show_time_setting(config_file)
    return Settings(
        data_directory=data_directory,
        config_file=config_file,
        show_time_in_datetime_picker=show_time_in_datetime_picker,
    )


def _load_show_time_setting(config_file: Path) -> bool:
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
    show_time = ui_settings.get("show_time_in_datetime_picker", False)
    if not isinstance(show_time, bool):
        raise ValueError(
            f"ui.show_time_in_datetime_picker in {config_file} must be true or false."
        )
    return show_time
