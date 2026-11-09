"""add actionable alerts

Revision ID: 0002_alerts
Revises: 0001_initial_schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_alerts"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    alert_type = sa.Enum("ENTRY_WARNING", "DWELL", name="alerttype", native_enum=False, create_constraint=True)
    severity = sa.Enum("WARNING", "HIGH", name="alertseverity", native_enum=False, create_constraint=True)
    status = sa.Enum("NEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED",
                     name="alertstatus", native_enum=False, create_constraint=True)
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=True),
        sa.Column("geofence_id", sa.Integer(), nullable=True),
        sa.Column("alert_type", alert_type, nullable=False),
        sa.Column("severity", severity, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("evidence_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("status", status, nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["video_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["monitoring_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["geofence_id"], ["geofences.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["evidence_snapshot_id"], ["snapshots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_alerts_event_id"),
    )
    op.create_index("ix_alerts_status_created", "alerts", ["status", "created_at"])
    op.create_index("ix_alerts_session_created", "alerts", ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_alerts_session_created", table_name="alerts")
    op.drop_index("ix_alerts_status_created", table_name="alerts")
    op.drop_table("alerts")
