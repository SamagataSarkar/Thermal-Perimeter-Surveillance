from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class SystemMetricCreate(BaseModel):
    source_id: int
    session_id: int
    recorded_at: datetime
    fps: Optional[float] = None
    inference_latency_ms: Optional[float] = None
    cpu_percent: Optional[float] = None
    gpu_percent: Optional[float] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class SystemMetricRead(SystemMetricCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
