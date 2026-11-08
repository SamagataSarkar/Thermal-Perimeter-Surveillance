import unittest
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import (
    Event,
    EventAuditLog,
    EventType,
    Geofence,
    MonitoringSession,
    Snapshot,
    SourceType,
    SystemMetric,
    VideoSource,
)
from backend.app.db.repositories.event_audit_logs import EventAuditLogRepository
from backend.app.db.repositories.events import EventRepository
from backend.app.db.repositories.geofences import GeofenceRepository
from backend.app.db.repositories.monitoring_sessions import MonitoringSessionRepository
from backend.app.db.repositories.snapshots import SnapshotRepository
from backend.app.db.repositories.system_metrics import SystemMetricRepository
from backend.app.db.repositories.video_sources import VideoSourceRepository
from backend.app.db.session import create_database_engine


class DatabasePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_repositories_persist_all_entity_types(self):
        source = VideoSource(name="Source", source_type=SourceType.RTSP, source_uri="rtsp://camera/live")
        VideoSourceRepository(self.session).add(source)
        session = MonitoringSessionRepository(self.session).add(
            MonitoringSession(source=source, configuration_snapshot={"zone_ids": []})
        )
        zone = Geofence(source=source, name="Zone", normalized_polygon=[[0, 0], [1, 0], [1, 1]])
        GeofenceRepository(self.session).add(zone)
        event = Event(
            source=source,
            session=session,
            geofence=zone,
            track_id=5,
            event_type=EventType.ENTRY,
            occurred_at=datetime.now(timezone.utc),
        )
        EventRepository(self.session).add(event)
        SnapshotRepository(self.session).add(
            Snapshot(source=source, session=session, event=event, file_path="event.jpg")
        )
        SystemMetricRepository(self.session).add(
            SystemMetric(source=source, session=session, fps=30)
        )
        EventAuditLogRepository(self.session).add(
            EventAuditLog(source=source, session=session, event=event, action="CREATED")
        )
        self.session.commit()

        self.assertIsNotNone(VideoSourceRepository(self.session).get(source.id))
        self.assertIsNotNone(MonitoringSessionRepository(self.session).get(session.id))
        self.assertIsNotNone(GeofenceRepository(self.session).get(zone.id))
        self.assertIsNotNone(EventRepository(self.session).get(event.id))

    def test_repeated_events_same_track_and_zone_are_allowed(self):
        source = VideoSource(name="Source", source_type=SourceType.FILE, source_uri="video.mp4")
        monitoring = MonitoringSession(source=source, configuration_snapshot={})
        zone = Geofence(source=source, name="Zone", normalized_polygon=[[0, 0], [1, 0], [1, 1]])
        self.session.add_all([source, monitoring, zone])
        self.session.flush()
        self.session.add_all([
            Event(source=source, session=monitoring, geofence=zone, track_id=1, event_type=EventType.ENTRY),
            Event(source=source, session=monitoring, geofence=zone, track_id=1, event_type=EventType.EXIT),
            Event(source=source, session=monitoring, geofence=zone, track_id=1, event_type=EventType.ENTRY),
        ])
        self.session.commit()
        self.assertEqual(self.session.query(Event).count(), 3)

    def test_idempotency_key_is_unique_only_when_present(self):
        source = VideoSource(name="Source", source_type=SourceType.FILE, source_uri="video.mp4")
        monitoring = MonitoringSession(source=source, configuration_snapshot={})
        self.session.add_all([source, monitoring])
        self.session.flush()
        self.session.add(Event(source=source, session=monitoring, event_type=EventType.ENTRY,
                               idempotency_key="occurrence-1"))
        self.session.commit()
        self.session.add(Event(source=source, session=monitoring, event_type=EventType.ENTRY,
                               idempotency_key="occurrence-1"))
        with self.assertRaises(IntegrityError):
            self.session.commit()


if __name__ == "__main__":
    unittest.main()
