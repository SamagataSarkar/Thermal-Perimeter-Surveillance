import unittest

from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import Event, EventType, MonitoringSession, SourceType, VideoSource
from backend.app.db.session import create_database_engine
from backend.app.schemas.geofences import GeofenceCreate


class DatabaseConstraintTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_normalized_polygon_is_validated(self):
        with self.assertRaises(ValidationError):
            GeofenceCreate(name="Invalid", normalized_polygon=[[0, 0], [2, 0], [1, 1]])

    def test_source_type_and_event_type_database_constraints(self):
        with Session(self.engine) as session:
            source = VideoSource(name="Source", source_type=SourceType.FILE, source_uri="video.mp4")
            session.add(source)
            session.flush()
            monitoring = MonitoringSession(source=source, configuration_snapshot={})
            session.add(monitoring)
            session.flush()
            event = Event(source=source, session=monitoring, event_type="INVALID")
            session.add(event)
            with self.assertRaises(Exception):
                session.commit()


if __name__ == "__main__":
    unittest.main()
