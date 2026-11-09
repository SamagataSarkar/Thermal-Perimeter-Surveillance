import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import cv2

from backend.app.config import MODEL_PATH, SNAPSHOT_DIRECTORY, TRACKER_CONFIG
from backend.app.core.connection_manager import ConnectionManager
from backend.app.db.models import (
    Event,
    EventStatus,
    EventType,
    EventAuditLog,
    MonitoringSession,
    Snapshot,
    SystemMetric,
    VideoSource,
)
from backend.app.db.session import create_session_factory, utc_now
from backend.app.schemas.video_sources import redact_source_uri
from scripts.inference.detector import Detector
from scripts.inference.events import EventType as InferenceEventType
from scripts.inference.geofence import PolygonZone
from scripts.inference.service import InferenceService
from scripts.inference.video_source import RecordedVideoSource, ThreadedLiveSource

logger = logging.getLogger(__name__)
_RTSP_CREDENTIALS = re.compile(r"rtsp://[^\s@]+@[^\s]+", re.IGNORECASE)


def _sanitize_error_message(message: str) -> str:
    return _RTSP_CREDENTIALS.sub(
        lambda match: redact_source_uri(match.group(0)), message
    )


@dataclass
class RuntimeSession:
    session_id: int
    source_id: int
    worker: Optional[threading.Thread] = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    frame_condition: threading.Condition = field(
        default_factory=lambda: threading.Condition(threading.RLock())
    )
    latest_frame: Optional[object] = None
    latest_jpeg: Optional[bytes] = None
    error: Optional[str] = None
    metrics: dict = field(default_factory=dict)

    def set_frame(self, frame, jpeg: bytes, metrics: dict) -> None:
        with self.frame_condition:
            self.latest_frame = frame.copy()
            self.latest_jpeg = jpeg
            self.metrics = metrics
            self.frame_condition.notify_all()

    def get_frame(self, timeout: float = 1.0):
        with self.frame_condition:
            if self.latest_jpeg is None:
                self.frame_condition.wait(timeout)
            return self.latest_jpeg


class RuntimeManager:
    def __init__(self, database_url: str, snapshot_directory: str = SNAPSHOT_DIRECTORY):
        self.engine, self.session_factory = create_session_factory(database_url)
        self.snapshot_directory = Path(snapshot_directory).resolve()
        self.snapshot_directory.mkdir(parents=True, exist_ok=True)
        self.connections = ConnectionManager()
        self._sessions: Dict[int, RuntimeSession] = {}
        self._lock = threading.RLock()

    @property
    def sessions(self) -> Dict[int, RuntimeSession]:
        with self._lock:
            return dict(self._sessions)

    def get(self, session_id: int) -> Optional[RuntimeSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def start(self, session: MonitoringSession, source: VideoSource, zones) -> RuntimeSession:
        with self._lock:
            if session.id in self._sessions:
                raise ValueError("monitoring session is already running")
            runtime = RuntimeSession(session.id, source.id)
            self._sessions[session.id] = runtime
        runtime.worker = threading.Thread(
            target=self._run, args=(runtime, session, source, zones),
            name="thermal-session-{}".format(session.id), daemon=True,
        )
        runtime.worker.start()
        return runtime

    def stop(self, session_id: int, wait: bool = True) -> None:
        runtime = self.get(session_id)
        if runtime is None:
            return
        runtime.stop_event.set()
        if wait and runtime.worker is not None:
            runtime.worker.join(timeout=10)

    def shutdown(self) -> None:
        for session_id in list(self.sessions):
            self.stop(session_id)
        self.engine.dispose()

    def _run(self, runtime, session, source, zones) -> None:
        db = self.session_factory()
        capture = None
        inference = None
        try:
            configuration = session.configuration_snapshot or {}
            detector = Detector(
                configuration.get("model_path", MODEL_PATH),
                configuration.get("tracker_config", TRACKER_CONFIG),
            )
            inference = InferenceService(
                detector,
                [PolygonZone(str(zone.id), tuple(map(tuple, zone.normalized_polygon))) for zone in zones],
                configuration.get("dwell_threshold", 3.0),
            )
            capture = (
                RecordedVideoSource(source.source_uri)
                if source.source_type.value == "FILE"
                else ThreadedLiveSource(source.source_uri)
            )
            with capture:
                while not runtime.stop_event.is_set():
                    packet = capture.read()
                    if packet is None:
                        if source.source_type.value == "FILE":
                            break
                        continue
                    started = time.monotonic()
                    annotated, events, result = inference.process_packet(packet)
                    encoded_ok, encoded = cv2.imencode(".jpg", annotated)
                    if not encoded_ok:
                        raise RuntimeError("unable to encode annotated frame")
                    metrics = {
                        "fps": inference.metrics.metrics.fps,
                        "inference_latency_ms": inference.metrics.metrics.inference_latency_ms,
                        "cpu_percent": None,
                        "gpu_percent": None,
                        "dropped_frames": 0,
                    }
                    runtime.set_frame(annotated, encoded.tobytes(), metrics)
                    self.connections.publish(session.id, self._message(
                        "detection_update", session.id,
                        {"frame_index": packet.frame_index, "metrics": metrics},
                    ))
                    for event in events:
                        self._persist_event(
                            db, runtime, session, source, event, annotated,
                            inference, result,
                        )
                    if inference.metrics.metrics.frames % 30 == 0:
                        self._persist_metrics(db, session, source, metrics)
                        self.connections.publish(
                            session.id, self._message("metrics_update", session.id, metrics)
                        )
            self._finish_session(db, session, "STOPPED")
        except Exception as exc:
            error_message = _sanitize_error_message(str(exc))
            runtime.error = error_message
            logger.error("Monitoring session %s failed: %s", session.id, error_message)
            self.connections.publish(
                session.id,
                self._message("source_error", session.id, {"message": error_message}),
            )
            self._finish_session(db, session, "FAILED")
        finally:
            runtime.stop_event.set()
            if inference is not None:
                try:
                    inference.reset()
                except Exception:
                    logger.exception("Failed to reset inference state for session %s", session.id)
            db.close()
            with self._lock:
                self._sessions.pop(session.id, None)

    def _persist_event(self, db, runtime, session, source, event, frame, inference, result):
        type_map = {
            InferenceEventType.PERIMETER_ENTRY.value: EventType.ENTRY,
            InferenceEventType.PERIMETER_EXIT.value: EventType.EXIT,
            InferenceEventType.DWELL_TIME_EXCEEDED.value: EventType.DWELL,
            InferenceEventType.FIRST_OBSERVED_INSIDE.value: EventType.FIRST_OBSERVED_INSIDE,
        }
        event_type = type_map.get(event.event_type)
        if event_type is None:
            return
        confidence = None
        object_class = None
        boxes = getattr(result, "boxes", None)
        if boxes is not None and boxes.id is not None:
            ids = boxes.id.int().cpu().tolist()
            confidences = boxes.conf.cpu().tolist()
            classes = boxes.cls.int().cpu().tolist()
            if event.track_id in ids:
                index = ids.index(event.track_id)
                confidence = float(confidences[index])
                object_class = inference.detector.class_names.get(classes[index])
        zone_id = int(event.zone_id) if str(event.zone_id).isdigit() else None
        key = "session:{}:{}:{}:{}".format(
            session.id, event.track_id, event.zone_id,
            "{}:{}".format(event.event_type, event.timestamp),
        )
        existing = db.query(Event).filter(Event.idempotency_key == key).first()
        if existing is not None:
            return
        persisted = Event(
            source_id=source.id,
            session_id=session.id,
            geofence_id=zone_id,
            track_id=event.track_id,
            event_type=event_type,
            status=EventStatus.NEW,
            occurred_at=utc_now(),
            idempotency_key=key,
            details={
                "inference_event_type": event.event_type,
                "class_id": event.class_id,
                "object_class": object_class,
                "confidence": confidence,
                **event.details,
            },
        )
        db.add(persisted)
        db.flush()
        try:
            self._save_snapshot(db, session, source, frame, persisted, False)
        except Exception:
            logger.exception("Unable to save automatic snapshot for event %s", persisted.id)
        db.commit()
        self.connections.publish(
            session.id,
            self._message("event_created", session.id, {"event_id": persisted.id}),
        )

    def _save_snapshot(self, db, session, source, frame, event, is_manual):
        filename = "{}_{}_{}.jpg".format(session.id, event.id if event else "manual", uuid.uuid4().hex)
        path = self.snapshot_directory / filename
        if not cv2.imwrite(str(path), frame):
            raise RuntimeError("unable to write snapshot")
        height, width = frame.shape[:2]
        snapshot = Snapshot(
            source_id=source.id,
            session_id=session.id,
            event_id=event.id if event else None,
            file_path=str(path),
            captured_at=utc_now(),
            is_manual=is_manual,
            width=width,
            height=height,
            metadata_json={"managed_storage": True},
        )
        db.add(snapshot)
        return snapshot

    def capture_snapshot(self, session_id: int) -> Snapshot:
        runtime = self.get(session_id)
        if runtime is None or runtime.latest_frame is None:
            raise ValueError("session has no annotated frame available")
        db = self.session_factory()
        try:
            session = db.get(MonitoringSession, session_id)
            if session is None:
                raise LookupError("monitoring session not found")
            source = db.get(VideoSource, session.source_id)
            snapshot = self._save_snapshot(db, session, source, runtime.latest_frame, None, True)
            db.commit()
            db.refresh(snapshot)
            return snapshot
        finally:
            db.close()

    def _persist_metrics(self, db, session, source, metrics):
        db.add(SystemMetric(
            source_id=source.id, session_id=session.id, recorded_at=utc_now(),
            fps=metrics.get("fps"), inference_latency_ms=metrics.get("inference_latency_ms"),
            cpu_percent=metrics.get("cpu_percent"),
            gpu_percent=metrics.get("gpu_percent"),
            metadata_json={"dropped_frames": metrics.get("dropped_frames", 0)},
        ))
        db.commit()

    def _finish_session(self, db, session, status):
        current = db.get(MonitoringSession, session.id)
        if current is not None and current.ended_at is None:
            current.status = status
            current.ended_at = utc_now()
            db.commit()
            self.connections.publish(session.id, self._message("session_status", session.id, {
                "status": status, "ended_at": current.ended_at,
            }))

    @staticmethod
    def _message(message_type, session_id, data):
        return {
            "type": message_type,
            "session_id": session_id,
            "timestamp": utc_now().isoformat(),
            "data": data,
        }
