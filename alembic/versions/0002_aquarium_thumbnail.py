"""Add an optional thumbnail to aquariums."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_aquarium_thumbnail"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("aquariums", sa.Column("thumbnail_data", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("aquariums", "thumbnail_data")
