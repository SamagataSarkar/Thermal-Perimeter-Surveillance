from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class MonitoringSessionCreate(BaseModel):
    source_id: int
    configuration_snapshot: Dict[str, Any]


class MonitoringSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    status: str
    configuration_snapshot: Dict[str, Any]
    started_at: datetime
    ended_at: Optional[datetime]
