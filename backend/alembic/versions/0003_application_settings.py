"""add persisted application settings

Revision ID: 0003_application_settings
Revises: 0002_alerts
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_application_settings"
down_revision: Union[str, Sequence[str], None] = "0002_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("application_settings")
