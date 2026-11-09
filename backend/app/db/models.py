from enum import Enum
from typing import Any, List, Optional

from sqlalchemy import Boolean, CheckConstraint, Enum as SqlEnum, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .session import UTCDateTime, utc_now


class SourceType(str, Enum):
    FILE = "FILE"
    RTSP = "RTSP"


class EventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    DWELL = "DWELL"
    FIRST_OBSERVED_INSIDE = "FIRST_OBSERVED_INSIDE"


class EventStatus(str, Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AlertType(str, Enum):
    ENTRY_WARNING = "ENTRY_WARNING"
    DWELL = "DWELL"


class AlertSeverity(str, Enum):
    WARNING = "WARNING"
    HIGH = "HIGH"


class AlertStatus(str, Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ApplicationSetting(Base):
    __tablename__ = "application_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_at: Mapped[Any] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class VideoSource(Base):
    __tablename__ = "video_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        SqlEnum(SourceType, native_enum=False, create_constraint=True), nullable=False
    )
    source_uri: Mapped[str] = mapped_column(String(2000), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[Any] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[Any] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)

    sessions: Mapped[List["MonitoringSession"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    geofences: Mapped[List["Geofence"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    events: Mapped[List["Event"]] = relationship(back_populates="source")
    snapshots: Mapped[List["Snapshot"]] = relationship(back_populates="source")
    metrics: Mapped[List["SystemMetric"]] = relationship(back_populates="source")
    audit_logs: Mapped[List["EventAuditLog"]] = relationship(back_populates="source")
    alerts: Mapped[List["Alert"]] = relationship(back_populates="source")

    def __repr__(self):
        return f"<VideoSource id={self.id!r} name={self.name!r} source_type={self.source_type!r}>"


class MonitoringSession(Base):
    __tablename__ = "monitoring_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("video_sources.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RUNNING")
    configuration_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    started_at: Mapped[Any] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    ended_at: Mapped[Optional[Any]] = mapped_column(UTCDateTime())

    source: Mapped["VideoSource"] = relationship(back_populates="sessions")
    events: Mapped[List["Event"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    snapshots: Mapped[List["Snapshot"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    metrics: Mapped[List["SystemMetric"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["EventAuditLog"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Geofence(Base):
    __tablename__ = "geofences"
    __table_args__ = (
        CheckConstraint("json_valid(normalized_polygon)", name="ck_geofences_polygon_json"),
        Index("ix_geofences_source_enabled", "source_id", "enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("video_sources.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_polygon: Mapped[list] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[Any] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[Any] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)

    source: Mapped["VideoSource"] = relationship(back_populates="geofences")
    events: Mapped[List["Event"]] = relationship(back_populates="geofence")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_events_idempotency_key"),
        Index("ix_events_session_occurred", "session_id", "occurred_at"),
        Index("ix_events_source_status", "source_id", "status"),
        Index("ix_events_track", "session_id", "track_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("video_sources.id", ondelete="RESTRICT"), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("monitoring_sessions.id", ondelete="CASCADE"), nullable=False)
    geofence_id: Mapped[Optional[int]] = mapped_column(ForeignKey("geofences.id", ondelete="SET NULL"))
    track_id: Mapped[Optional[int]] = mapped_column(Integer)
    event_type: Mapped[EventType] = mapped_column(
        SqlEnum(EventType, native_enum=False, create_constraint=True), nullable=False
    )
    status: Mapped[EventStatus] = mapped_column(
        SqlEnum(EventStatus, native_enum=False, create_constraint=True),
        nullable=False,
        default=EventStatus.NEW,
    )
    occurred_at: Mapped[Any] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    source: Mapped["VideoSource"] = relationship(back_populates="events")
    session: Mapped["MonitoringSession"] = relationship(back_populates="events")
    geofence: Mapped[Optional["Geofence"]] = relationship(back_populates="events")
    snapshots: Mapped[List["Snapshot"]] = relationship(back_populates="event")
    audit_logs: Mapped[List["EventAuditLog"]] = relationship(back_populates="event")
    alert: Mapped[Optional["Alert"]] = relationship(back_populates="event", uselist=False)


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (
        Index("ix_snapshots_session_captured", "session_id", "captured_at"),
        CheckConstraint(
            "(event_id IS NOT NULL) OR (is_manual = 1)",
            name="ck_snapshots_event_or_manual",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("video_sources.id", ondelete="RESTRICT"), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("monitoring_sessions.id", ondelete="CASCADE"), nullable=False)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    file_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    captured_at: Mapped[Any] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="image/jpeg")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    source: Mapped["VideoSource"] = relationship(back_populates="snapshots")
    session: Mapped["MonitoringSession"] = relationship(back_populates="snapshots")
    event: Mapped[Optional["Event"]] = relationship(back_populates="snapshots")
    alerts: Mapped[List["Alert"]] = relationship(back_populates="evidence_snapshot")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_alerts_event_id"),
        Index("ix_alerts_status_created", "status", "created_at"),
        Index("ix_alerts_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("video_sources.id", ondelete="RESTRICT"), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("monitoring_sessions.id", ondelete="CASCADE"), nullable=False)
    track_id: Mapped[Optional[int]] = mapped_column(Integer)
    geofence_id: Mapped[Optional[int]] = mapped_column(ForeignKey("geofences.id", ondelete="SET NULL"))
    alert_type: Mapped[AlertType] = mapped_column(
        SqlEnum(AlertType, native_enum=False, create_constraint=True), nullable=False
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        SqlEnum(AlertSeverity, native_enum=False, create_constraint=True), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    evidence_snapshot_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("snapshots.id", ondelete="SET NULL")
    )
    created_at: Mapped[Any] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    acknowledged_at: Mapped[Optional[Any]] = mapped_column(UTCDateTime())
    resolved_at: Mapped[Optional[Any]] = mapped_column(UTCDateTime())
    status: Mapped[AlertStatus] = mapped_column(
        SqlEnum(AlertStatus, native_enum=False, create_constraint=True),
        nullable=False,
        default=AlertStatus.NEW,
    )

    event: Mapped["Event"] = relationship(back_populates="alert")
    source: Mapped["VideoSource"] = relationship(back_populates="alerts")
    evidence_snapshot: Mapped[Optional["Snapshot"]] = relationship(back_populates="alerts")


class SystemMetric(Base):
    __tablename__ = "system_metrics"
    __table_args__ = (
        Index("ix_metrics_session_recorded", "session_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("video_sources.id", ondelete="RESTRICT"), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("monitoring_sessions.id", ondelete="CASCADE"), nullable=False)
    recorded_at: Mapped[Any] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    fps: Mapped[Optional[float]]
    inference_latency_ms: Mapped[Optional[float]]
    cpu_percent: Mapped[Optional[float]]
    gpu_percent: Mapped[Optional[float]]
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    source: Mapped["VideoSource"] = relationship(back_populates="metrics")
    session: Mapped["MonitoringSession"] = relationship(back_populates="metrics")


class EventAuditLog(Base):
    __tablename__ = "event_audit_logs"
    __table_args__ = (
        Index("ix_audit_event_created", "event_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("video_sources.id", ondelete="RESTRICT"), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("monitoring_sessions.id", ondelete="CASCADE"), nullable=False)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[Any] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    source: Mapped["VideoSource"] = relationship(back_populates="audit_logs")
    session: Mapped["MonitoringSession"] = relationship(back_populates="audit_logs")
    event: Mapped[Optional["Event"]] = relationship(back_populates="audit_logs")
