from pathlib import Path

from alembic import command
from alembic.config import Config


def upgrade_database(database_url: str, project_root: Path) -> None:
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")
