import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.app.db.base import Base
from backend.app.db.models import (
    Event,
    MonitoringSession,
    Snapshot,
    SourceType,
    SystemMetric,
    VideoSource,
)
from backend.app.db.session import utc_now
from backend.app.main import create_app
from backend.app.services.runtime import RuntimeSession
from scripts.inference.models import FramePacket, InferenceEvent


class FakeResult:
    boxes = None


class FakeDetector:
    class_names = {0: "person"}

    def __init__(self, *args):
        pass

    def reset(self):
        pass


class FakeInference:
    def __init__(self, detector, zones, dwell_threshold, **kwargs):
        self.detector = detector
        self.metrics = type(
            "MetricsContainer",
            (),
            {
                "metrics": type(
                    "Metrics",
                    (),
                    {"fps": 24.0, "inference_latency_ms": 4.5, "frames": 0},
                )()
            },
        )()

    def process_packet(self, packet):
        self.metrics.metrics.frames += 1
        return packet.frame.copy(), [], FakeResult()

    def reset(self):
        pass


class BackendIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = Path(self.temp_dir.name) / "integration.db"
        self.app = create_app("sqlite:///" + str(database))
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.db = self.app.state.runtime.session_factory()
        self.source = VideoSource(
            name="Demo", source_type=SourceType.FILE, source_uri="demo.mp4"
        )
        self.db.add(self.source)
        self.db.flush()
        self.session = MonitoringSession(
            source_id=self.source.id,
            status="RUNNING",
            configuration_snapshot={},
        )
        self.db.add(self.session)
        self.db.commit()
        self.db.refresh(self.source)
        self.db.refresh(self.session)
        self.runtime_session = RuntimeSession(self.session.id, self.source.id)
        self.app.state.runtime._sessions[self.session.id] = self.runtime_session

    def tearDown(self):
        self.app.state.runtime._sessions.clear()
        self.db.close()
        self.client.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def test_websocket_broadcasts_to_multiple_clients_and_cleans_up(self):
        with self.client.websocket_connect(
            "/ws/monitor/{}".format(self.session.id)
        ) as first, self.client.websocket_connect(
            "/ws/monitor/{}".format(self.session.id)
        ) as second:
            self.app.state.runtime.connections.publish(
                self.session.id,
                {
                    "type": "session_status",
                    "session_id": self.session.id,
                    "data": {"status": "RUNNING"},
                },
            )
            self.app.state.runtime.connections.publish(
                self.session.id,
                {
                    "type": "event_created",
                    "session_id": self.session.id,
                    "data": {"event_id": 7},
                },
            )
            self.assertEqual(first.receive_json()["type"], "session_status")
            self.assertEqual(second.receive_json()["type"], "session_status")
            self.assertEqual(first.receive_json()["type"], "event_created")
            self.assertEqual(second.receive_json()["type"], "event_created")
        self.assertNotIn(
            self.session.id, self.app.state.runtime.connections._clients
        )

    def test_disconnected_websocket_does_not_break_broadcast(self):
        with self.client.websocket_connect(
            "/ws/monitor/{}".format(self.session.id)
        ) as websocket:
            websocket.close()
        self.app.state.runtime.connections.publish(
            self.session.id,
            {"type": "event_created", "session_id": self.session.id, "data": {}},
        )
        self.assertNotIn(
            self.session.id, self.app.state.runtime.connections._clients
        )

    def test_session_stop_broadcasts_terminal_notification(self):
        client = object()
        queue = self.app.state.runtime.connections.connect(self.session.id, client)
        self.app.state.runtime._finish_session(self.db, self.session, "STOPPED")
        messages = [json.loads(queue.get_nowait()), json.loads(queue.get_nowait())]
        self.assertEqual(messages[0]["type"], "session_status")
        self.assertEqual(messages[1]["type"], "session_stopped")
        self.assertEqual(messages[1]["session_id"], self.session.id)
        self.app.state.runtime.connections.disconnect(self.session.id, client)

    def test_mjpeg_stream_uses_existing_frame_and_handles_stopped_session(self):
        frame = np.zeros((12, 16, 3), dtype=np.uint8)
        encoded, jpeg = cv2.imencode(".jpg", frame)
        self.assertTrue(encoded)
        self.runtime_session.set_frame(frame, jpeg.tobytes(), {})
        stream_route = next(
            route for route in self.app.routes
            if route.path == "/api/stream/{session_id}"
        )
        response = stream_route.endpoint(self.session.id)

        async def read_one():
            async for chunk in response.body_iterator:
                self.assertIn(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n", chunk)
                self.assertIn(jpeg.tobytes(), chunk)
                self.runtime_session.stop_event.set()
                break
            await response.body_iterator.aclose()

        asyncio.run(read_one())
        self.runtime_session.stop_event.set()
        stopped_response = stream_route.endpoint(self.session.id)

        async def read_stopped():
            chunks = [chunk async for chunk in stopped_response.body_iterator]
            self.assertEqual(chunks, [])

        asyncio.run(read_stopped())
        self.app.state.runtime._sessions.pop(self.session.id)
        self.assertEqual(
            self.client.get("/api/stream/{}".format(self.session.id)).status_code,
            404,
        )

    def test_automatic_and_manual_snapshots_and_safe_retrieval(self):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        self.runtime_session.set_frame(frame, b"jpeg", {})
        inference_event = InferenceEvent(
            event_type="PERIMETER_ENTRY",
            track_id=3,
            zone_id="not-a-database-zone",
            timestamp=1.0,
            class_id=0,
        )
        manager = self.app.state.runtime
        manager._persist_event(
            self.db,
            self.runtime_session,
            self.session,
            self.source,
            inference_event,
            frame,
            FakeInference(FakeDetector(), [], 3.0),
            FakeResult(),
        )
        event = self.db.query(Event).one()
        self.assertEqual(event.details["inference_timestamp"], 1.0)
        self.assertEqual(event.occurred_at.tzinfo, utc_now().tzinfo)
        snapshot = self.db.query(Snapshot).filter(Snapshot.event_id == event.id).one()
        self.assertTrue(Path(snapshot.file_path).is_file())
        self.db.commit()

        manual = manager.capture_snapshot(self.session.id)
        self.assertTrue(manual.is_manual)
        self.assertIsNone(manual.event_id)
        self.assertTrue(Path(manual.file_path).is_file())

        outside = Path(self.temp_dir.name) / "outside.jpg"
        outside.write_bytes(b"not an image")
        unsafe = Snapshot(
            source_id=self.source.id,
            session_id=self.session.id,
            file_path=str(outside),
            captured_at=utc_now(),
            is_manual=True,
        )
        self.db.add(unsafe)
        self.db.commit()
        self.assertEqual(
            self.client.get("/api/snapshots/{}/image".format(unsafe.id)).status_code,
            400,
        )

    def test_snapshot_write_failure_does_not_fail_event_persistence(self):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        event = InferenceEvent(
            event_type="PERIMETER_ENTRY",
            track_id=4,
            zone_id="zone",
            timestamp=2.0,
            class_id=0,
        )
        manager = self.app.state.runtime
        with patch("backend.app.services.runtime.cv2.imwrite", return_value=False):
            manager._persist_event(
                self.db,
                self.runtime_session,
                self.session,
                self.source,
                event,
                frame,
                FakeInference(FakeDetector(), [], 3.0),
                FakeResult(),
            )
        self.assertEqual(self.db.query(Event).count(), 1)
        self.assertEqual(self.db.query(Snapshot).count(), 0)

    def test_metrics_keep_unavailable_hardware_metrics_as_none(self):
        manager = self.app.state.runtime
        manager._persist_metrics(
            self.db,
            self.session,
            self.source,
            {
                "fps": 24.0,
                "inference_latency_ms": 4.5,
                "cpu_percent": None,
                "gpu_percent": None,
                "dropped_frames": 0,
            },
        )
        metric = self.db.query(SystemMetric).one()
        self.assertEqual(metric.fps, 24.0)
        self.assertEqual(metric.inference_latency_ms, 4.5)
        self.assertIsNone(metric.cpu_percent)
        self.assertIsNone(metric.gpu_percent)
        metrics_response = self.client.get(
            "/api/sessions/{}/metrics".format(self.session.id)
        )
        self.assertEqual(metrics_response.status_code, 200)
        self.assertEqual(metrics_response.json()[0]["fps"], 24.0)

    def test_rtsp_worker_errors_redact_credentials(self):
        source = self.db.get(VideoSource, self.source.id)
        source.source_type = SourceType.RTSP
        source.source_uri = "rtsp://user:p%40ss@camera.local/live"
        self.db.commit()
        session = self.db.get(MonitoringSession, self.session.id)
        self.app.state.runtime._sessions.pop(self.session.id)

        class FailingCapture:
            def __init__(self, source_uri):
                self.source_uri = source_uri

            def __enter__(self):
                raise RuntimeError("Unable to open {}".format(self.source_uri))

            def __exit__(self, *args):
                pass

        with patch("backend.app.services.runtime.Detector", FakeDetector), patch(
            "backend.app.services.runtime.InferenceService", FakeInference
        ), patch(
            "backend.app.services.runtime.ThreadedLiveSource", FailingCapture
        ):
            runtime = self.app.state.runtime.start(session, source, [])
            runtime.worker.join(5)
        self.assertNotIn("p%40ss", runtime.error)
        self.assertNotIn("user:", runtime.error)
        self.assertIn("REDACTED", runtime.error)

    def test_recorded_video_worker_cleans_up_with_mocked_inference(self):
        video = Path(__file__).parents[1] / "demo_thermal.mp4"
        if not video.is_file():
            self.skipTest("demo thermal video is unavailable")
        source = self.db.get(VideoSource, self.source.id)
        source.source_uri = str(video)
        self.db.commit()
        session = self.db.get(MonitoringSession, self.session.id)
        configured_model_path = Path(self.temp_dir.name) / "configured-model.pt"
        configured_model_path.touch()
        session.configuration_snapshot = {
            "model_path": str(configured_model_path),
            "tracker_config": "unused",
        }
        self.db.commit()
        self.app.state.runtime._sessions.pop(self.session.id)
        with patch("backend.app.services.runtime.Detector", autospec=True) as detector_class, patch(
            "backend.app.services.runtime.InferenceService", FakeInference
        ):
            runtime = self.app.state.runtime.start(session, source, [])
            runtime.worker.join(10)
        detector_class.assert_called_once_with(str(configured_model_path.resolve()), "unused")
        check_db = self.app.state.runtime.session_factory()
        check = check_db.get(MonitoringSession, self.session.id)
        self.assertFalse(runtime.worker.is_alive())
        self.assertEqual(check.status, "STOPPED")
        self.assertIsNotNone(runtime.latest_jpeg)
        self.assertIsNone(self.app.state.runtime.get(self.session.id))
        check_db.close()


if __name__ == "__main__":
    unittest.main()
