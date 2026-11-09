import asyncio
import logging
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from backend.app.config import (
    APPLICATION_VERSION,
    DATABASE_URL,
    ENTRY_DEBOUNCE_SECONDS,
    EXIT_DEBOUNCE_SECONDS,
    GEOFENCE_HYSTERESIS_PIXELS,
    INFERENCE_SIZE,
    DEFAULT_DWELL_THRESHOLD_SECONDS,
    MIN_DWELL_THRESHOLD_SECONDS,
    MAX_DWELL_THRESHOLD_SECONDS,
    MODEL_PATH,
    TRACKER_CONFIG,
    TRANSITION_MIN_OBSERVATIONS,
    resolve_model_path,
)
from backend.app.core.connection_manager import ConnectionManager
from backend.app.db.base import Base
from backend.app.db.models import (
    Event,
    Alert,
    AlertStatus,
    ApplicationSetting,
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
from backend.app.db.session import utc_now
from backend.app.schemas.geofences import GeofenceCreate, GeofenceRead
from backend.app.schemas.alerts import AlertRead
from backend.app.schemas.video_sources import (
    SourceTypeSchema,
    VideoSourceCreate,
    VideoSourceRead,
    redact_source_uri,
)
from backend.app.services.runtime import RuntimeManager

logger = logging.getLogger(__name__)


class SourceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    source_uri: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    enabled: Optional[bool] = None


class ZoneUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    normalized_polygon: Optional[list[tuple[float, float]]] = None
    enabled: Optional[bool] = None


class SessionStart(BaseModel):
    source_id: int
    zone_ids: Optional[List[int]] = None
    model_path: Optional[str] = None
    tracker_config: Optional[str] = None
    dwell_threshold: Optional[float] = Field(default=None, gt=0, le=MAX_DWELL_THRESHOLD_SECONDS)


class DwellThresholdUpdate(BaseModel):
    dwell_threshold: float = Field(gt=MIN_DWELL_THRESHOLD_SECONDS, le=MAX_DWELL_THRESHOLD_SECONDS)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_id: int
    status: str
    configuration_snapshot: dict
    started_at: object
    ended_at: Optional[object]


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_id: int
    session_id: int
    geofence_id: Optional[int]
    track_id: Optional[int]
    event_type: EventType
    status: EventStatus
    occurred_at: object
    details: dict


class SnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_id: int
    session_id: int
    event_id: Optional[int]
    file_path: str
    captured_at: object
    is_manual: bool
    width: Optional[int]
    height: Optional[int]
    mime_type: str


def _validate_polygon(polygon):
    if polygon is None or len(polygon) < 3:
        raise HTTPException(422, "A polygon requires at least three points")
    if any(not (0 <= x <= 1 and 0 <= y <= 1) for x, y in polygon):
        raise HTTPException(422, "polygon coordinates must be between 0 and 1")


def _validate_source_uri(source_type, source_uri):
    if source_type == SourceType.FILE:
        if not Path(source_uri).is_file():
            raise HTTPException(422, "recorded video path does not exist")
        return
    parsed = urlsplit(source_uri)
    if parsed.scheme.lower() != "rtsp" or not parsed.hostname:
        raise HTTPException(422, "source_uri must be a valid RTSP URL")


def _serialize_source(source):
    return {
        "id": source.id,
        "name": source.name,
        "source_type": source.source_type,
        "source_uri": redact_source_uri(source.source_uri),
        "enabled": source.enabled,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }

def _serialize_zone(zone):
    return {
        "id": zone.id,
        "source_id": zone.source_id,
        "name": zone.name,
        "normalized_polygon": zone.normalized_polygon,
        "enabled": zone.enabled,
        "created_at": zone.created_at,
        "updated_at": zone.updated_at,
    }


def _serialize_session(session):
    return SessionRead.model_validate(session).model_dump(mode="json")


def _serialize_alert(alert):
    result = AlertRead.model_validate(alert).model_dump(mode="json")
    if result["evidence_snapshot_id"] is None and alert.event is not None:
        snapshot = min(alert.event.snapshots, key=lambda item: item.id, default=None)
        if snapshot is not None:
            result["evidence_snapshot_id"] = snapshot.id
    if alert.event is not None:
        class_id = alert.event.details.get("class_id")
        result["class_id"] = class_id
        result["object_class"] = alert.event.details.get("object_class") or {
            0: "person",
            1: "vehicle",
        }.get(class_id)
        result["observed_dwell_seconds"] = alert.event.details.get("dwell_seconds")
        result["dwell_threshold"] = (
            alert.event.session.configuration_snapshot or {}
        ).get("dwell_threshold")
    return result


def _ensure_sqlite_parent(database_url):
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        path = Path(database_url[len(prefix):])
        if str(path) not in (":memory:", ""):
            path.parent.mkdir(parents=True, exist_ok=True)


def create_app(database_url: str = DATABASE_URL) -> FastAPI:
    _ensure_sqlite_parent(database_url)
    runtime = RuntimeManager(database_url)
    engine = runtime.engine
    Base.metadata.create_all(engine)
    app = FastAPI(
        title="Thermal Perimeter Surveillance",
        version=APPLICATION_VERSION,
        description="Backend API for object detection and intrusion monitoring.",
    )
    app.state.engine = engine
    app.state.runtime = runtime

    def db_session():
        return runtime.session_factory()

    def get_dwell_threshold(db):
        setting = db.get(ApplicationSetting, "dwell_threshold_seconds")
        if setting is None:
            return DEFAULT_DWELL_THRESHOLD_SECONDS
        return float(setting.value)

    @app.get("/api/settings")
    def get_settings():
        db = db_session()
        try:
            return {"dwell_threshold": get_dwell_threshold(db)}
        finally:
            db.close()

    @app.put("/api/settings/dwell-threshold")
    def update_dwell_threshold(payload: DwellThresholdUpdate):
        db = db_session()
        try:
            setting = db.get(ApplicationSetting, "dwell_threshold_seconds")
            if setting is None:
                setting = ApplicationSetting(
                    key="dwell_threshold_seconds",
                    value=str(payload.dwell_threshold),
                )
                db.add(setting)
            else:
                setting.value = str(payload.dwell_threshold)
            db.commit()
            return {"dwell_threshold": payload.dwell_threshold}
        finally:
            db.close()

    @app.on_event("shutdown")
    def shutdown():
        runtime.shutdown()
        engine.dispose()

    @app.get("/api/health")
    def health():
        db_ok = True
        try:
            with engine.connect() as connection:
                connection.execute(select(1))
        except Exception:
            db_ok = False
        return {
            "status": "ok" if db_ok else "degraded",
            "database": {"connected": db_ok},
            "active_sessions": len(runtime.sessions),
            "inference_available": bool(MODEL_PATH),
            "version": APPLICATION_VERSION,
        }

    @app.get("/api/sources")
    def list_sources():
        db = db_session()
        try:
            return [_serialize_source(source) for source in db.scalars(select(VideoSource)).all()]
        finally:
            db.close()

    @app.post("/api/sources", status_code=201)
    def create_source(payload: VideoSourceCreate):
        _validate_source_uri(SourceType(payload.source_type.value), payload.source_uri)
        db = db_session()
        try:
            source = VideoSource(
                name=payload.name,
                source_type=SourceType(payload.source_type.value),
                source_uri=payload.source_uri,
                enabled=payload.enabled,
            )
            db.add(source)
            db.commit()
            db.refresh(source)
            return _serialize_source(source)
        finally:
            db.close()

    @app.get("/api/sources/{source_id}")
    def get_source(source_id: int):
        db = db_session()
        try:
            source = db.get(VideoSource, source_id)
            if source is None:
                raise HTTPException(404, "source not found")
            return _serialize_source(source)
        finally:
            db.close()

    @app.put("/api/sources/{source_id}")
    def update_source(source_id: int, payload: SourceUpdate):
        db = db_session()
        try:
            source = db.get(VideoSource, source_id)
            if source is None:
                raise HTTPException(404, "source not found")
            if runtime.sessions and source_id in [item.source_id for item in runtime.sessions.values()]:
                raise HTTPException(409, "source has an active monitoring session")
            values = payload.model_dump(exclude_unset=True)
            if "source_uri" in values:
                _validate_source_uri(source.source_type, values["source_uri"])
            for name, value in values.items():
                setattr(source, name, value)
            db.commit()
            db.refresh(source)
            return _serialize_source(source)
        finally:
            db.close()

    @app.delete("/api/sources/{source_id}")
    def delete_source(source_id: int):
        db = db_session()
        try:
            source = db.get(VideoSource, source_id)
            if source is None:
                raise HTTPException(404, "source not found")
            if runtime.sessions and source_id in [item.source_id for item in runtime.sessions.values()]:
                raise HTTPException(409, "source has an active monitoring session")
            if source.sessions or source.events or source.snapshots:
                raise HTTPException(409, "source has historical records")
            db.delete(source)
            db.commit()
            return {"deleted": True}
        finally:
            db.close()

    @app.get("/api/zones")
    def list_zones(source_id: Optional[int] = None):
        db = db_session()
        try:
            query = select(Geofence)
            if source_id is not None:
                query = query.where(Geofence.source_id == source_id)
            return [_serialize_zone(zone) for zone in db.scalars(query).all()]
        finally:
            db.close()

    @app.post("/api/zones", status_code=201)
    def create_zone(payload: GeofenceCreate, source_id: Optional[int] = Query(None)):
        _validate_polygon(payload.normalized_polygon)
        source_id = source_id or payload.source_id
        if source_id is None:
            raise HTTPException(422, "source_id is required")
        db = db_session()
        try:
            if db.get(VideoSource, source_id) is None:
                raise HTTPException(404, "source not found")
            zone = Geofence(
                source_id=source_id, name=payload.name,
                normalized_polygon=payload.normalized_polygon, enabled=payload.enabled,
            )
            db.add(zone)
            db.commit()
            db.refresh(zone)
            return _serialize_zone(zone)
        finally:
            db.close()

    @app.get("/api/zones/{zone_id}")
    def get_zone(zone_id: int):
        db = db_session()
        try:
            zone = db.get(Geofence, zone_id)
            if zone is None:
                raise HTTPException(404, "zone not found")
            return _serialize_zone(zone)
        finally:
            db.close()

    @app.put("/api/zones/{zone_id}")
    def update_zone(zone_id: int, payload: ZoneUpdate):
        db = db_session()
        try:
            zone = db.get(Geofence, zone_id)
            if zone is None:
                raise HTTPException(404, "zone not found")
            if any(zone.id in [
                int(item) for item in (session.configuration_snapshot or {}).get("zone_ids", [])
            ] for session in db.scalars(
                select(MonitoringSession).where(MonitoringSession.status == "RUNNING")
            ).all()):
                raise HTTPException(409, "zone is used by an active session")
            values = payload.model_dump(exclude_unset=True)
            if "normalized_polygon" in values:
                _validate_polygon(values["normalized_polygon"])
            for name, value in values.items():
                setattr(zone, name, value)
            db.commit()
            db.refresh(zone)
            return _serialize_zone(zone)
        finally:
            db.close()

    @app.delete("/api/zones/{zone_id}")
    def delete_zone(zone_id: int):
        db = db_session()
        try:
            zone = db.get(Geofence, zone_id)
            if zone is None:
                raise HTTPException(404, "zone not found")
            if zone.events:
                raise HTTPException(409, "zone has historical events")
            db.delete(zone)
            db.commit()
            return {"deleted": True}
        finally:
            db.close()

    @app.post("/api/sessions/start", status_code=201)
    def start_session(payload: SessionStart):
        db = db_session()
        try:
            model_path = resolve_model_path(payload.model_path)
            if not Path(model_path).is_file():
                raise HTTPException(
                    422,
                    "configured model file does not exist: {}".format(model_path),
                )
            source = db.get(VideoSource, payload.source_id)
            if source is None:
                raise HTTPException(404, "source not found")
            if not source.enabled:
                raise HTTPException(409, "source is disabled")
            _validate_source_uri(source.source_type, source.source_uri)
            active = db.scalars(select(MonitoringSession).where(
                MonitoringSession.source_id == source.id,
                MonitoringSession.status == "RUNNING",
            )).first()
            if active is not None or any(
                item.source_id == source.id for item in runtime.sessions.values()
            ):
                raise HTTPException(409, "source already has an active monitoring session")
            enabled_zones = db.scalars(select(Geofence).where(
                Geofence.source_id == source.id, Geofence.enabled.is_(True)
            )).all()
            if payload.zone_ids is None:
                zones = enabled_zones
            else:
                selected_ids = set(payload.zone_ids)
                if len(selected_ids) != len(payload.zone_ids):
                    raise HTTPException(422, "zone_ids must not contain duplicates")
                zones_by_id = {zone.id: zone for zone in enabled_zones}
                invalid_ids = sorted(selected_ids - zones_by_id.keys())
                if invalid_ids:
                    raise HTTPException(
                        422,
                        "selected zones must belong to the source and be enabled: {}".format(
                            invalid_ids
                        ),
                    )
                zones = [zones_by_id[zone_id] for zone_id in payload.zone_ids]
            config = {
                "model_path": model_path,
                "tracker_config": payload.tracker_config or TRACKER_CONFIG,
                "dwell_threshold": (
                    payload.dwell_threshold
                    if payload.dwell_threshold is not None
                    else get_dwell_threshold(db)
                ),
                "entry_debounce_seconds": ENTRY_DEBOUNCE_SECONDS,
                "exit_debounce_seconds": EXIT_DEBOUNCE_SECONDS,
                "transition_min_observations": TRANSITION_MIN_OBSERVATIONS,
                "geofence_hysteresis_pixels": GEOFENCE_HYSTERESIS_PIXELS,
                "inference_size": INFERENCE_SIZE,
                "zone_ids": [zone.id for zone in zones],
            }
            session = MonitoringSession(
                source_id=source.id, status="RUNNING", configuration_snapshot=config,
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            runtime.start(session, source, zones)
            runtime.connections.publish(session.id, {
                "type": "session_status", "session_id": session.id,
                "timestamp": utc_now().isoformat(), "data": {"status": "RUNNING"},
            })
            return _serialize_session(session)
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Unable to start monitoring session")
            raise HTTPException(500, "unable to start monitoring session") from exc
        finally:
            db.close()

    @app.post("/api/sessions/{session_id}/stop")
    def stop_session(session_id: int):
        db = db_session()
        try:
            session = db.get(MonitoringSession, session_id)
            if session is None:
                raise HTTPException(404, "monitoring session not found")
            runtime.stop(session_id)
            if session.ended_at is None:
                session.status = "STOPPED"
                session.ended_at = utc_now()
                db.commit()
            db.refresh(session)
            return _serialize_session(session)
        finally:
            db.close()

    @app.get("/api/sessions")
    def list_sessions():
        db = db_session()
        try:
            return [_serialize_session(item) for item in db.scalars(
                select(MonitoringSession).order_by(MonitoringSession.started_at.desc())
            ).all()]
        finally:
            db.close()

    @app.get("/api/sessions/active")
    def get_active_session():
        db = db_session()
        try:
            sessions = db.scalars(select(MonitoringSession).where(
                MonitoringSession.status == "RUNNING"
            ).order_by(MonitoringSession.started_at.desc())).all()
            for session in sessions:
                if runtime.get(session.id) is not None:
                    return _serialize_session(session)
            return None
        finally:
            db.close()

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: int):
        db = db_session()
        try:
            session = db.get(MonitoringSession, session_id)
            if session is None:
                raise HTTPException(404, "monitoring session not found")
            return _serialize_session(session)
        finally:
            db.close()

    @app.get("/api/events")
    def list_events(
        session_id: Optional[int] = None, source_id: Optional[int] = None,
        zone_id: Optional[int] = None, event_type: Optional[EventType] = None,
        status: Optional[EventStatus] = None, offset: int = 0, limit: int = Query(50, le=200),
    ):
        db = db_session()
        try:
            query = select(Event).order_by(Event.occurred_at.desc()).offset(offset).limit(limit)
            if session_id is not None:
                query = query.where(Event.session_id == session_id)
            if source_id is not None:
                query = query.where(Event.source_id == source_id)
            if zone_id is not None:
                query = query.where(Event.geofence_id == zone_id)
            if event_type is not None:
                query = query.where(Event.event_type == event_type)
            if status is not None:
                query = query.where(Event.status == status)
            return [EventRead.model_validate(item).model_dump(mode="json") for item in db.scalars(query).all()]
        finally:
            db.close()

    @app.get("/api/events/{event_id}")
    def get_event(event_id: int):
        db = db_session()
        try:
            event = db.get(Event, event_id)
            if event is None:
                raise HTTPException(404, "event not found")
            return EventRead.model_validate(event).model_dump(mode="json")
        finally:
            db.close()

    @app.get("/api/alerts")
    def list_alerts(
        session_id: Optional[int] = None,
        status: Optional[AlertStatus] = None,
        offset: int = 0,
        limit: int = Query(50, le=200),
    ):
        db = db_session()
        try:
            query = select(Alert).order_by(Alert.created_at.desc()).offset(offset).limit(limit)
            if session_id is not None:
                query = query.where(Alert.session_id == session_id)
            if status is not None:
                query = query.where(Alert.status == status)
            return [_serialize_alert(item) for item in db.scalars(query).all()]
        finally:
            db.close()

    @app.get("/api/alerts/{alert_id}")
    def get_alert(alert_id: int):
        db = db_session()
        try:
            alert = db.get(Alert, alert_id)
            if alert is None:
                raise HTTPException(404, "alert not found")
            return _serialize_alert(alert)
        finally:
            db.close()

    def update_alert_status(alert_id, status, action):
        db = db_session()
        try:
            alert = db.get(Alert, alert_id)
            if alert is None:
                raise HTTPException(404, "alert not found")
            allowed = {
                AlertStatus.NEW: {AlertStatus.ACKNOWLEDGED, AlertStatus.RESOLVED, AlertStatus.DISMISSED},
                AlertStatus.ACKNOWLEDGED: {AlertStatus.RESOLVED, AlertStatus.DISMISSED},
            }
            if status not in allowed.get(alert.status, set()):
                raise HTTPException(409, "alert status cannot be changed from {}".format(alert.status.value))
            if status == AlertStatus.ACKNOWLEDGED:
                alert.acknowledged_at = utc_now()
            elif status in (AlertStatus.RESOLVED, AlertStatus.DISMISSED):
                alert.resolved_at = utc_now()
            alert.status = status
            db.commit()
            db.refresh(alert)
            runtime.connections.publish(alert.session_id, {
                "type": "alert_updated",
                "session_id": alert.session_id,
                "timestamp": utc_now().isoformat(),
                "data": {"alert_id": alert.id, "status": alert.status.value},
            })
            return _serialize_alert(alert)
        finally:
            db.close()

    @app.post("/api/alerts/{alert_id}/acknowledge")
    def acknowledge_alert(alert_id: int):
        return update_alert_status(alert_id, AlertStatus.ACKNOWLEDGED, "acknowledged")

    @app.post("/api/alerts/{alert_id}/resolve")
    def resolve_alert(alert_id: int):
        return update_alert_status(alert_id, AlertStatus.RESOLVED, "resolved")

    @app.post("/api/alerts/{alert_id}/dismiss")
    def dismiss_alert(alert_id: int):
        return update_alert_status(alert_id, AlertStatus.DISMISSED, "dismissed")

    def update_event_status(event_id, status, action):
        db = db_session()
        try:
            event = db.get(Event, event_id)
            if event is None:
                raise HTTPException(404, "event not found")
            event.status = status
            db.add(EventAuditLog(
                source_id=event.source_id, session_id=event.session_id,
                event_id=event.id, action=action, actor="api",
                created_at=utc_now(), details={"status": status.value},
            ))
            db.commit()
            runtime.connections.publish(event.session_id, {
                "type": "event_" + action.lower(), "session_id": event.session_id,
                "timestamp": utc_now().isoformat(), "data": {"event_id": event.id},
            })
            return EventRead.model_validate(event).model_dump(mode="json")
        finally:
            db.close()

    @app.post("/api/events/{event_id}/acknowledge")
    def acknowledge_event(event_id: int):
        return update_event_status(event_id, EventStatus.ACKNOWLEDGED, "acknowledged")

    @app.post("/api/events/{event_id}/resolve")
    def resolve_event(event_id: int):
        return update_event_status(event_id, EventStatus.RESOLVED, "resolved")

    @app.get("/api/sessions/{session_id}/metrics")
    def session_metrics(session_id: int, limit: int = Query(100, le=500)):
        db = db_session()
        try:
            if db.get(MonitoringSession, session_id) is None:
                raise HTTPException(404, "monitoring session not found")
            rows = db.scalars(select(SystemMetric).where(
                SystemMetric.session_id == session_id
            ).order_by(SystemMetric.recorded_at.desc()).limit(limit)).all()
            runtime_session = runtime.get(session_id)
            result = [row.__dict__ for row in rows]
            for row in result:
                row.pop("_sa_instance_state", None)
            if runtime_session is not None and runtime_session.metrics:
                result.insert(0, {"live": True, **runtime_session.metrics})
            return result
        finally:
            db.close()

    @app.get("/api/snapshots")
    def list_snapshots(session_id: Optional[int] = None, limit: int = Query(100, le=500)):
        db = db_session()
        try:
            query = select(Snapshot).order_by(Snapshot.captured_at.desc()).limit(limit)
            if session_id is not None:
                query = query.where(Snapshot.session_id == session_id)
            return [SnapshotRead.model_validate(item).model_dump(mode="json") for item in db.scalars(query).all()]
        finally:
            db.close()

    @app.post("/api/snapshots/capture", status_code=201)
    def capture_snapshot(session_id: int = Query(...)):
        try:
            return SnapshotRead.model_validate(
                runtime.capture_snapshot(session_id)
            ).model_dump(mode="json")
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/snapshots/{snapshot_id}/image")
    def snapshot_image(snapshot_id: int):
        db = db_session()
        try:
            snapshot = db.get(Snapshot, snapshot_id)
            if snapshot is None:
                raise HTTPException(404, "snapshot not found")
            path = Path(snapshot.file_path).resolve()
            if runtime.snapshot_directory not in path.parents:
                raise HTTPException(400, "invalid snapshot path")
            if not path.is_file():
                raise HTTPException(404, "snapshot file not found")
            return FileResponse(path, media_type=snapshot.mime_type)
        finally:
            db.close()

    @app.websocket("/ws/monitor/{session_id}")
    async def monitor_websocket(websocket: WebSocket, session_id: int):
        if runtime.get(session_id) is None:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        client_queue = runtime.connections.connect(session_id, websocket)
        try:
            while True:
                message = await runtime.connections.receive(client_queue)
                if message:
                    await websocket.send_text(message)
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                except asyncio.TimeoutError:
                    pass
        except WebSocketDisconnect:
            pass
        finally:
            runtime.connections.disconnect(session_id, websocket)

    @app.get("/api/stream/{session_id}")
    def stream(session_id: int):
        runtime_session = runtime.get(session_id)
        if runtime_session is None:
            raise HTTPException(404, "active monitoring session not found")

        def frames():
            while not runtime_session.stop_event.is_set():
                frame = runtime_session.get_frame(1.0)
                if frame is None:
                    if runtime_session.error:
                        break
                    continue
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"

        return StreamingResponse(
            frames(), media_type="multipart/x-mixed-replace; boundary=frame"
        )

    return app


app = create_app()
