from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.app.db.models import EventStatus, EventType


class EventCreate(BaseModel):
    source_id: int
    session_id: int
    geofence_id: Optional[int] = None
    track_id: Optional[int] = None
    event_type: EventType
    status: EventStatus = EventStatus.NEW
    occurred_at: datetime
    idempotency_key: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class EventRead(EventCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
