import unittest
from datetime import datetime, timezone

from sqlalchemy import event as sqlalchemy_event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import (
    Event,
    EventAuditLog,
    EventStatus,
    EventType,
    Geofence,
    MonitoringSession,
    Snapshot,
    SourceType,
    SystemMetric,
    VideoSource,
)
from backend.app.db.session import create_database_engine


class DatabaseModelTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_all_entities_relationships_and_persistence(self):
        source = VideoSource(
            name="Thermal camera",
            source_type=SourceType.FILE,
            source_uri="demo_thermal2.mp4",
        )
        source.geofences.extend([
            Geofence(name="North", normalized_polygon=[[0, 0], [0.5, 0], [0.5, 1]]),
            Geofence(name="South", normalized_polygon=[[0.5, 0], [1, 0], [1, 1]]),
        ])
        monitoring = MonitoringSession(
            status="RUNNING",
            configuration_snapshot={"dwell_seconds": 3},
        )
        source.sessions.append(monitoring)
        self.session.add(source)
        self.session.flush()

        event = Event(
            source=source,
            session=monitoring,
            geofence=source.geofences[0],
            track_id=7,
            event_type=EventType.ENTRY,
            status=EventStatus.NEW,
            occurred_at=datetime(2026, 11, 8, tzinfo=timezone.utc),
        )
        self.session.add(event)
        monitoring.snapshots.extend([
            Snapshot(source=source, event=event, file_path="snapshots/event.jpg"),
            Snapshot(source=source, is_manual=True, file_path="snapshots/manual.jpg"),
        ])
        monitoring.metrics.append(
            SystemMetric(source=source, fps=24.0, inference_latency_ms=12.5)
        )
        monitoring.audit_logs.append(
            EventAuditLog(source=source, event=event, action="CREATED")
        )
        self.session.commit()

        loaded = self.session.get(VideoSource, source.id)
        self.assertEqual(len(loaded.geofences), 2)
        self.assertEqual(loaded.sessions[0].events[0].geofence.name, "North")
        self.assertEqual(len(loaded.sessions[0].snapshots), 2)
        self.assertEqual(len(loaded.sessions[0].metrics), 1)
        self.assertEqual(loaded.sessions[0].audit_logs[0].event.id, event.id)

    def test_utc_timestamp_round_trip(self):
        source = VideoSource(
            name="UTC source",
            source_type=SourceType.FILE,
            source_uri="video.mp4",
            created_at=datetime(2026, 11, 8, 12, 0),
        )
        self.session.add(source)
        self.session.commit()
        loaded = self.session.get(VideoSource, source.id)
        self.assertEqual(loaded.created_at.tzinfo, timezone.utc)
        self.assertEqual(loaded.created_at.hour, 12)

    def test_sqlite_foreign_keys_are_enabled(self):
        self.assertEqual(self.session.execute(text("PRAGMA foreign_keys")).scalar(), 1)
        self.session.add(MonitoringSession(source_id=999, configuration_snapshot={}))
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_manual_snapshot_requires_no_event_but_non_manual_does(self):
        source = VideoSource(name="Source", source_type=SourceType.FILE, source_uri="video.mp4")
        source.sessions.append(MonitoringSession(configuration_snapshot={}))
        self.session.add(source)
        self.session.flush()
        invalid = Snapshot(
            source=source,
            session=source.sessions[0],
            file_path="invalid.jpg",
            is_manual=False,
        )
        self.session.add(invalid)
        with self.assertRaises(IntegrityError):
            self.session.commit()


if __name__ == "__main__":
    unittest.main()
