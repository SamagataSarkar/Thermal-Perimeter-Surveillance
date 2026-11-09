from typing import Optional

from backend.app.core.connection_manager import ConnectionManager
from backend.app.db.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertType,
    Event,
    EventType,
    Snapshot,
)
from backend.app.db.session import utc_now


class AlertRuleEngine:
    """Create one actionable alert for each supported confirmed event."""

    def __init__(self, connections: Optional[ConnectionManager] = None):
        self.connections = connections

    def create_for_event(self, db, event: Event, snapshot: Optional[Snapshot] = None):
        class_id = event.details.get("class_id")
        if class_id not in (0, 1):
            return None
        if event.event_type not in (EventType.ENTRY, EventType.DWELL):
            return None
        existing = db.query(Alert).filter(Alert.event_id == event.id).first()
        if existing is not None:
            if existing.evidence_snapshot_id is None and snapshot is not None:
                existing.evidence_snapshot_id = snapshot.id
            return existing
        object_name = "person" if class_id == 0 else "vehicle"
        alert_type = AlertType.ENTRY_WARNING if event.event_type == EventType.ENTRY else AlertType.DWELL
        severity = AlertSeverity.WARNING if event.event_type == EventType.ENTRY else AlertSeverity.HIGH
        title = "Possible {} intrusion".format(object_name)
        description = (
            "Possible {} intrusion in the restricted zone; operator verification required."
            .format(object_name)
        )
        alert = Alert(
            event_id=event.id,
            source_id=event.source_id,
            session_id=event.session_id,
            track_id=event.track_id,
            geofence_id=event.geofence_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            description=description,
            evidence_snapshot_id=snapshot.id if snapshot is not None else None,
            created_at=utc_now(),
            status=AlertStatus.NEW,
        )
        db.add(alert)
        db.flush()
        return alert


class AlertService:
    def __init__(self, connections: Optional[ConnectionManager] = None):
        self.rules = AlertRuleEngine(connections)
        self.connections = connections

    def process_event(self, db, event: Event, snapshot: Optional[Snapshot] = None):
        existing = db.query(Alert).filter(Alert.event_id == event.id).first()
        alert = self.rules.create_for_event(db, event, snapshot)
        if alert is not None and existing is None and self.connections is not None:
            self.connections.publish(event.session_id, {
                "type": "alert_created",
                "session_id": event.session_id,
                "timestamp": alert.created_at.isoformat(),
                "data": {
                    "alert_id": alert.id,
                    "event_id": event.id,
                    "alert_type": alert.alert_type.value,
                    "severity": alert.severity.value,
                    "status": alert.status.value,
                    "class_id": event.details.get("class_id"),
                    "object_class": event.details.get("object_class"),
                },
            })
        return alert
