from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class EventAuditLogCreate(BaseModel):
    source_id: int
    session_id: int
    event_id: Optional[int] = None
    action: str
    actor: Optional[str] = None
    created_at: datetime
    details: Dict[str, Any] = Field(default_factory=dict)


class EventAuditLogRead(EventAuditLogCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
