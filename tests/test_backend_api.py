import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.db.models import Event, EventStatus, EventType, MonitoringSession, VideoSource, SourceType
from backend.app.main import create_app
from backend.app.db.session import utc_now


class BackendApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = Path(self.temp_dir.name) / "api.db"
        self.app = create_app("sqlite:///" + str(database))
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.video = Path(self.temp_dir.name) / "video.mp4"
        self.video.touch()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def test_health_source_and_zone_crud(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        response = self.client.post("/api/sources", json={
            "name": "Demo", "source_type": "FILE", "source_uri": str(self.video),
        })
        self.assertEqual(response.status_code, 201)
        source_id = response.json()["id"]
        response = self.client.post("/api/zones", json={
            "source_id": source_id, "name": "Perimeter",
            "normalized_polygon": [[0, 0], [1, 0], [1, 1]],
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["source_id"], source_id)

    def test_rtsp_credentials_are_not_returned(self):
        response = self.client.post("/api/sources", json={
            "name": "Camera", "source_type": "RTSP",
            "source_uri": "rtsp://user:p%40ss@camera.local/live",
        })
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("p%40ss", response.json()["source_uri"])
        self.assertNotIn("user:", response.json()["source_uri"])

    def test_event_status_change_is_audited(self):
        db = self.app.state.runtime.session_factory()
        source = VideoSource(
            name="Demo", source_type=SourceType.FILE, source_uri=str(self.video)
        )
        db.add(source)
        db.flush()
        session = MonitoringSession(
            source_id=source.id, status="STOPPED", configuration_snapshot={},
            ended_at=utc_now(),
        )
        db.add(session)
        db.flush()
        event = Event(
            source_id=source.id, session_id=session.id, event_type=EventType.ENTRY,
            occurred_at=utc_now(), details={},
        )
        db.add(event)
        db.commit()
        event_id = event.id
        db.close()
        response = self.client.post("/api/events/{}/acknowledge".format(event_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ACKNOWLEDGED")
        db = self.app.state.runtime.session_factory()
        self.assertEqual(db.get(Event, event_id).status, EventStatus.ACKNOWLEDGED)
        self.assertEqual(len(db.get(Event, event_id).audit_logs), 1)
        db.close()


if __name__ == "__main__":
    unittest.main()
