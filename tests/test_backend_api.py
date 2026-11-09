import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.app.db.models import Alert, AlertSeverity, AlertStatus, AlertType, Event, EventStatus, EventType, Geofence, MonitoringSession, Snapshot, VideoSource, SourceType
from backend.app.services.alerts import AlertService
from backend.app.config import (
    ENTRY_DEBOUNCE_SECONDS,
    EXIT_DEBOUNCE_SECONDS,
    GEOFENCE_HYSTERESIS_PIXELS,
    INFERENCE_SIZE,
    MODEL_PATH,
    TRANSITION_MIN_OBSERVATIONS,
)
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

    def test_alert_rules_and_status_endpoints(self):
        db = self.app.state.runtime.session_factory()
        source = VideoSource(name="Demo", source_type=SourceType.FILE, source_uri=str(self.video))
        db.add(source)
        db.flush()
        session = MonitoringSession(source_id=source.id, status="STOPPED", configuration_snapshot={})
        db.add(session)
        db.flush()
        entry = Event(
            source_id=source.id, session_id=session.id, event_type=EventType.ENTRY,
            occurred_at=utc_now(), details={"class_id": 0, "object_class": "person"},
        )
        first = Event(
            source_id=source.id, session_id=session.id,
            event_type=EventType.FIRST_OBSERVED_INSIDE, occurred_at=utc_now(), details={},
        )
        db.add_all([entry, first])
        db.flush()
        service = AlertService(self.app.state.runtime.connections)
        alert = service.process_event(db, entry)
        self.assertIsNotNone(alert)
        self.assertIsNone(service.process_event(db, first))
        self.assertIs(service.process_event(db, entry), alert)
        db.commit()
        alert_id = alert.id
        db.close()

        response = self.client.get("/api/alerts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        response = self.client.post("/api/alerts/{}/acknowledge".format(alert_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ACKNOWLEDGED")
        client = object()
        queue = self.app.state.runtime.connections.connect(session.id, client)
        response = self.client.post("/api/alerts/{}/resolve".format(alert_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(queue.get_nowait())["type"], "alert_updated")
        self.app.state.runtime.connections.disconnect(session.id, client)
        response = self.client.post("/api/alerts/{}/dismiss".format(alert_id))
        self.assertEqual(response.status_code, 409)

    def test_person_vehicle_alert_rules_reject_animals_and_deduplicate(self):
        db = self.app.state.runtime.session_factory()
        source = VideoSource(name="Demo", source_type=SourceType.FILE, source_uri=str(self.video))
        db.add(source)
        db.flush()
        session = MonitoringSession(source_id=source.id, status="STOPPED", configuration_snapshot={})
        db.add(session)
        db.flush()
        events = [
            Event(source_id=source.id, session_id=session.id, event_type=EventType.ENTRY,
                  occurred_at=utc_now(), details={"class_id": 0, "object_class": "person"}),
            Event(source_id=source.id, session_id=session.id, event_type=EventType.ENTRY,
                  occurred_at=utc_now(), details={"class_id": 1, "object_class": "vehicle"}),
            Event(source_id=source.id, session_id=session.id, event_type=EventType.DWELL,
                  occurred_at=utc_now(), details={"class_id": 0, "object_class": "person", "dwell_seconds": 3.0}),
            Event(source_id=source.id, session_id=session.id, event_type=EventType.DWELL,
                  occurred_at=utc_now(), details={"class_id": 1, "object_class": "vehicle", "dwell_seconds": 3.0}),
            Event(source_id=source.id, session_id=session.id, event_type=EventType.DWELL,
                  occurred_at=utc_now(), details={"class_id": 2, "object_class": "animal"}),
        ]
        db.add_all(events)
        db.flush()
        service = AlertService(self.app.state.runtime.connections)
        client = object()
        queue = self.app.state.runtime.connections.connect(session.id, client)
        alerts = [service.process_event(db, event) for event in events]
        self.assertEqual([alert.alert_type.value if alert else None for alert in alerts],
                         ["ENTRY_WARNING", "ENTRY_WARNING", "DWELL", "DWELL", None])
        self.assertEqual(alerts[0].severity.value, "WARNING")
        self.assertEqual(alerts[2].severity.value, "HIGH")
        self.assertEqual(alerts[3].severity.value, "HIGH")
        messages = [json.loads(queue.get_nowait()) for _ in range(4)]
        self.assertTrue(any(
            message["type"] == "alert_created"
            and message["data"]["alert_id"] == alerts[3].id
            and message["data"]["severity"] == "HIGH"
            for message in messages
        ))
        self.assertEqual(service.process_event(db, events[3]).id, alerts[3].id)
        self.assertEqual(db.query(Alert).count(), 4)
        self.app.state.runtime.connections.disconnect(session.id, client)
        db.rollback()
        db.close()

    def test_session_uses_requested_enabled_zones_and_snapshots_configuration(self):
        db = self.app.state.runtime.session_factory()
        source = VideoSource(name="Demo", source_type=SourceType.FILE, source_uri=str(self.video))
        other_source = VideoSource(name="Other", source_type=SourceType.FILE, source_uri=str(self.video))
        db.add_all([source, other_source])
        db.flush()
        zones = [
            Geofence(source_id=source.id, name="North", normalized_polygon=[[0, 0], [1, 0], [1, 1]]),
            Geofence(source_id=source.id, name="South", normalized_polygon=[[0, 0], [0, 1], [1, 1]]),
            Geofence(source_id=source.id, name="Disabled", normalized_polygon=[[0, 0], [1, 0], [0, 1]], enabled=False),
            Geofence(source_id=other_source.id, name="Foreign", normalized_polygon=[[0, 0], [1, 0], [0, 1]]),
        ]
        db.add_all(zones)
        db.commit()
        source_id = source.id
        north_id, south_id, disabled_id, foreign_id = [zone.id for zone in zones]
        db.close()

        for invalid_id in (disabled_id, foreign_id):
            response = self.client.post("/api/sessions/start", json={
                "source_id": source_id, "zone_ids": [invalid_id],
            })
            self.assertEqual(response.status_code, 422)

        with patch.object(self.app.state.runtime, "start") as start:
            response = self.client.post("/api/sessions/start", json={
                "source_id": source_id, "zone_ids": [south_id, north_id],
            })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["configuration_snapshot"]["zone_ids"], [south_id, north_id])
        selected_zones = start.call_args.args[2]
        self.assertEqual([zone.id for zone in selected_zones], [south_id, north_id])

    def test_omitted_zone_ids_selects_all_enabled_zones(self):
        db = self.app.state.runtime.session_factory()
        source = VideoSource(name="Demo", source_type=SourceType.FILE, source_uri=str(self.video))
        db.add(source)
        db.flush()
        enabled = Geofence(source_id=source.id, name="Enabled", normalized_polygon=[[0, 0], [1, 0], [1, 1]])
        disabled = Geofence(source_id=source.id, name="Disabled", normalized_polygon=[[0, 0], [1, 0], [0, 1]], enabled=False)
        db.add_all([enabled, disabled])
        db.commit()
        source_id = source.id
        enabled_id = enabled.id
        db.close()

        with patch.object(self.app.state.runtime, "start") as start:
            response = self.client.post("/api/sessions/start", json={"source_id": source_id})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["configuration_snapshot"]["zone_ids"], [enabled_id])

    def test_session_records_resolved_default_model_path(self):
        db = self.app.state.runtime.session_factory()
        source = VideoSource(name="Demo", source_type=SourceType.FILE, source_uri=str(self.video))
        db.add(source)
        db.commit()
        source_id = source.id
        db.close()

        with patch.object(self.app.state.runtime, "start"):
            response = self.client.post("/api/sessions/start", json={"source_id": source_id})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["configuration_snapshot"]["model_path"], MODEL_PATH)
        snapshot = response.json()["configuration_snapshot"]
        self.assertEqual(snapshot["entry_debounce_seconds"], ENTRY_DEBOUNCE_SECONDS)
        self.assertEqual(snapshot["exit_debounce_seconds"], EXIT_DEBOUNCE_SECONDS)
        self.assertEqual(snapshot["transition_min_observations"], TRANSITION_MIN_OBSERVATIONS)
        self.assertEqual(snapshot["geofence_hysteresis_pixels"], GEOFENCE_HYSTERESIS_PIXELS)
        self.assertEqual(snapshot["inference_size"], INFERENCE_SIZE)

    def test_missing_model_file_returns_clear_error(self):
        response = self.client.post("/api/sessions/start", json={
            "source_id": 999999,
            "model_path": "does-not-exist.pt",
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn("configured model file does not exist", response.json()["detail"])

    def test_dwell_threshold_setting_persists_and_is_used_by_new_sessions(self):
        response = self.client.get("/api/settings")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["dwell_threshold"], 3.0)
        response = self.client.put("/api/settings/dwell-threshold", json={"dwell_threshold": 7.5})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["dwell_threshold"], 7.5)
        self.assertEqual(self.client.get("/api/settings").json()["dwell_threshold"], 7.5)

    def test_alert_evidence_uses_event_snapshot_and_serves_image(self):
        image_path = self.app.state.runtime.snapshot_directory / (
            "test_evidence_{}.jpg".format(self.id().replace(".", "_"))
        )
        self.assertTrue(cv2.imwrite(str(image_path), np.zeros((20, 30, 3), dtype=np.uint8)))
        db = self.app.state.runtime.session_factory()
        source = VideoSource(name="Demo", source_type=SourceType.FILE, source_uri=str(self.video))
        db.add(source)
        db.flush()
        session = MonitoringSession(source_id=source.id, status="STOPPED", configuration_snapshot={"dwell_threshold": 3.0})
        db.add(session)
        db.flush()
        event = Event(
            source_id=source.id, session_id=session.id, event_type=EventType.DWELL,
            occurred_at=utc_now(), details={"class_id": 0, "dwell_seconds": 3.2},
        )
        db.add(event)
        db.flush()
        snapshot = Snapshot(
            source_id=source.id, session_id=session.id, event_id=event.id,
            file_path=str(image_path), captured_at=utc_now(), is_manual=False,
            width=30, height=20, mime_type="image/jpeg", metadata_json={},
        )
        db.add(snapshot)
        db.flush()
        alert = AlertService(self.app.state.runtime.connections).process_event(
            db, event, snapshot
        )
        db.commit()
        alert_id = alert.id
        snapshot_id = snapshot.id
        db.close()
        response = self.client.get("/api/alerts/{}".format(alert_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["evidence_snapshot_id"], snapshot_id)
        image = self.client.get("/api/snapshots/{}/image".format(snapshot_id))
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers["content-type"], "image/jpeg")
        image_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
