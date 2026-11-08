from enum import Enum
from typing import Dict, Iterable, List, Tuple

from .models import InferenceEvent, TrackObservation, TrackState


class EventType(str, Enum):
    PERIMETER_ENTRY = "PERIMETER_ENTRY"
    PERIMETER_EXIT = "PERIMETER_EXIT"
    FIRST_OBSERVED_INSIDE = "FIRST_OBSERVED_INSIDE"
    DWELL_TIME_EXCEEDED = "DWELL_TIME_EXCEEDED"


class EventEngine:
    def __init__(self, dwell_threshold: float = 3.0, loss_grace_period: float = 1.0):
        if dwell_threshold < 0 or loss_grace_period < 0:
            raise ValueError("Timing thresholds must not be negative")
        self.dwell_threshold = dwell_threshold
        self.loss_grace_period = loss_grace_period
        self._states: Dict[Tuple[int, str], TrackState] = {}

    def update(
        self,
        observations: Iterable[TrackObservation],
        zones,
        frame_size: Tuple[int, int],
        timestamp: float,
    ) -> List[InferenceEvent]:
        width, height = frame_size
        events = []
        seen = set()
        for observation in observations:
            for zone in zones:
                key = (observation.track_id, zone.zone_id)
                inside = zone.contains(observation.point, width, height)
                seen.add(key)
                state = self._states.get(key)
                if state is None:
                    state = TrackState(
                        inside=inside,
                        first_inside_at=timestamp if inside else None,
                        last_seen_at=timestamp,
                    )
                    self._states[key] = state
                    if inside:
                        events.append(self._event(
                            EventType.FIRST_OBSERVED_INSIDE, observation, zone.zone_id, timestamp
                        ))
                else:
                    if not state.inside and inside:
                        state.first_inside_at = timestamp
                        state.dwell_alerted = False
                        events.append(self._event(
                            EventType.PERIMETER_ENTRY, observation, zone.zone_id, timestamp
                        ))
                    elif state.inside and not inside:
                        events.append(self._event(
                            EventType.PERIMETER_EXIT, observation, zone.zone_id, timestamp
                        ))
                        state.first_inside_at = None
                        state.dwell_alerted = False
                    state.inside = inside
                    state.last_seen_at = timestamp
                state.missing_since = None
                if (state.inside and state.first_inside_at is not None
                        and not state.dwell_alerted
                        and timestamp - state.first_inside_at >= self.dwell_threshold):
                    state.dwell_alerted = True
                    events.append(self._event(
                        EventType.DWELL_TIME_EXCEEDED, observation, zone.zone_id, timestamp,
                        {"dwell_seconds": timestamp - state.first_inside_at},
                    ))

        for key, state in list(self._states.items()):
            if key not in seen:
                if state.missing_since is None:
                    state.missing_since = timestamp
                elif timestamp - state.missing_since > self.loss_grace_period:
                    del self._states[key]
        return events

    def reset(self):
        self._states.clear()

    @property
    def state_count(self):
        return len(self._states)

    @staticmethod
    def _event(event_type, observation, zone_id, timestamp, details=None):
        return InferenceEvent(
            event_type=event_type.value,
            track_id=observation.track_id,
            zone_id=zone_id,
            timestamp=timestamp,
            class_id=observation.class_id,
            details=details or {},
        )
