import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import URL


@dataclass(frozen=True)
class Settings:
    data_directory: Path

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
    return Settings(data_directory=data_directory)
