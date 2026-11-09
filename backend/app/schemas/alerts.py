from typing import Optional

from pydantic import BaseModel, ConfigDict

from backend.app.db.models import AlertSeverity, AlertStatus, AlertType


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    source_id: int
    session_id: int
    track_id: Optional[int]
    geofence_id: Optional[int]
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    evidence_snapshot_id: Optional[int]
    created_at: object
    acknowledged_at: Optional[object]
    resolved_at: Optional[object]
    status: AlertStatus
    object_class: Optional[str] = None
    class_id: Optional[int] = None
    dwell_threshold: Optional[float] = None
    observed_dwell_seconds: Optional[float] = None
