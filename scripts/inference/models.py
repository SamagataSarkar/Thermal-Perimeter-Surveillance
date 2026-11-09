from dataclasses import dataclass, field
from typing import Any, FrozenSet, Optional, Tuple

Point = Tuple[int, int]


@dataclass(frozen=True)
class FramePacket:
    frame: Any
    timestamp: float
    frame_index: int


@dataclass(frozen=True)
class TrackObservation:
    track_id: int
    class_id: int
    confidence: float
    box: Tuple[int, int, int, int]
    point: Point


@dataclass(frozen=True)
class TrackerLifecycle:
    tracked_ids: FrozenSet[int]
    lost_ids: FrozenSet[int]
    removed_ids: FrozenSet[int]


@dataclass(frozen=True)
class InferenceEvent:
    event_type: str
    track_id: int
    zone_id: str
    timestamp: float
    class_id: int
    details: dict = field(default_factory=dict)


@dataclass
class TrackState:
    inside: bool
    first_inside_at: Optional[float] = None
    dwell_alerted: bool = False
    last_seen_at: float = 0.0
    missing_since: Optional[float] = None
    candidate_inside: Optional[bool] = None
    candidate_started_at: Optional[float] = None
    candidate_observations: int = 0
