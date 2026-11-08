"""create initial backend schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    source_type = sa.Enum("FILE", "RTSP", name="sourcetype", native_enum=False, create_constraint=True)
    event_type = sa.Enum("ENTRY", "EXIT", "DWELL", "FIRST_OBSERVED_INSIDE",
                         name="eventtype", native_enum=False, create_constraint=True)
    event_status = sa.Enum("NEW", "ACKNOWLEDGED", "RESOLVED",
                           name="eventstatus", native_enum=False, create_constraint=True)

    op.create_table(
        "video_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("source_uri", sa.String(length=2000), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "monitoring_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("configuration_snapshot", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["video_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "geofences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_polygon", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("json_valid(normalized_polygon)", name="ck_geofences_polygon_json"),
        sa.ForeignKeyConstraint(["source_id"], ["video_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_geofences_source_enabled", "geofences", ["source_id", "enabled"])
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("geofence_id", sa.Integer(), nullable=True),
        sa.Column("track_id", sa.Integer(), nullable=True),
        sa.Column("event_type", event_type, nullable=False),
        sa.Column("status", event_status, nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.CheckConstraint("idempotency_key IS NULL OR length(idempotency_key) > 0",
                           name="ck_events_idempotency_key"),
        sa.ForeignKeyConstraint(["geofence_id"], ["geofences.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["monitoring_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["video_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_events_idempotency_key"),
    )
    op.create_index("ix_events_session_occurred", "events", ["session_id", "occurred_at"])
    op.create_index("ix_events_source_status", "events", ["source_id", "status"])
    op.create_index("ix_events_track", "events", ["session_id", "track_id"])
    op.create_table(
        "snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("file_path", sa.String(length=2000), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("is_manual", sa.Boolean(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.CheckConstraint("(event_id IS NOT NULL) OR (is_manual = 1)",
                           name="ck_snapshots_event_or_manual"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["monitoring_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["video_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_snapshots_session_captured", "snapshots", ["session_id", "captured_at"])
    op.create_table(
        "system_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("fps", sa.Float(), nullable=True),
        sa.Column("inference_latency_ms", sa.Float(), nullable=True),
        sa.Column("cpu_percent", sa.Float(), nullable=True),
        sa.Column("gpu_percent", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["monitoring_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["video_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metrics_session_recorded", "system_metrics", ["session_id", "recorded_at"])
    op.create_table(
        "event_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["monitoring_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["video_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_event_created", "event_audit_logs", ["event_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_event_created", table_name="event_audit_logs")
    op.drop_table("event_audit_logs")
    op.drop_index("ix_metrics_session_recorded", table_name="system_metrics")
    op.drop_table("system_metrics")
    op.drop_index("ix_snapshots_session_captured", table_name="snapshots")
    op.drop_table("snapshots")
    op.drop_index("ix_events_track", table_name="events")
    op.drop_index("ix_events_source_status", table_name="events")
    op.drop_index("ix_events_session_occurred", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_geofences_source_enabled", table_name="geofences")
    op.drop_table("geofences")
    op.drop_table("monitoring_sessions")
    op.drop_table("video_sources")
