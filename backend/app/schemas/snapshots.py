from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class SnapshotCreate(BaseModel):
    source_id: int
    session_id: int
    event_id: Optional[int] = None
    file_path: str = Field(min_length=1, max_length=2000)
    captured_at: datetime
    is_manual: bool = False
    width: Optional[int] = None
    height: Optional[int] = None
    mime_type: str = "image/jpeg"
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class SnapshotRead(SnapshotCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
