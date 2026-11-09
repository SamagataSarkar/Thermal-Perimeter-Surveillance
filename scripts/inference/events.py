from enum import Enum
from typing import Dict, Iterable, List, Tuple

from .models import InferenceEvent, TrackObservation, TrackState, TrackerLifecycle


class EventType(str, Enum):
    PERIMETER_ENTRY = "PERIMETER_ENTRY"
    PERIMETER_EXIT = "PERIMETER_EXIT"
    FIRST_OBSERVED_INSIDE = "FIRST_OBSERVED_INSIDE"
    DWELL_TIME_EXCEEDED = "DWELL_TIME_EXCEEDED"


class EventEngine:
    def __init__(
        self,
        dwell_threshold: float = 3.0,
        loss_grace_period: float = 1.0,
        entry_debounce: float = 0.15,
        exit_debounce: float = 0.25,
        min_transition_observations: int = 3,
        hysteresis_margin: float = 4.0,
    ):
        if (
            dwell_threshold < 0
            or loss_grace_period < 0
            or entry_debounce < 0
            or exit_debounce < 0
            or min_transition_observations < 1
            or hysteresis_margin < 0
        ):
            raise ValueError("Timing thresholds must not be negative")
        self.dwell_threshold = dwell_threshold
        self.loss_grace_period = loss_grace_period
        self.entry_debounce = entry_debounce
        self.exit_debounce = exit_debounce
        self.min_transition_observations = min_transition_observations
        self.hysteresis_margin = hysteresis_margin
        self._states: Dict[Tuple[int, str], TrackState] = {}

    def update(
        self,
        observations: Iterable[TrackObservation],
        zones,
        frame_size: Tuple[int, int],
        timestamp: float,
        lifecycle: TrackerLifecycle = None,
    ) -> List[InferenceEvent]:
        width, height = frame_size
        events = []
        seen = set()
        for observation in observations:
            for zone in zones:
                key = (observation.track_id, zone.zone_id)
                seen.add(key)
                state = self._states.get(key)
                if state is None:
                    inside = zone.contains(observation.point, width, height)
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
                    observation_gap = None
                    if state.missing_since is not None:
                        observation_gap = max(0.0, timestamp - state.last_seen_at)
                        if observation_gap > self.loss_grace_period:
                            state.first_inside_at = timestamp
                    distance = zone.signed_distance(observation.point, width, height)
                    transition_inside = self._transition_membership(
                        state, distance, timestamp
                    )
                    if transition_inside is not None:
                        event_timestamp = state.candidate_started_at
                        state.inside = transition_inside
                        state.candidate_inside = None
                        state.candidate_started_at = None
                        state.candidate_observations = 0
                        if transition_inside:
                            state.first_inside_at = timestamp
                            state.dwell_alerted = False
                            events.append(self._event(
                                EventType.PERIMETER_ENTRY,
                                observation,
                                zone.zone_id,
                                event_timestamp,
                            ))
                        else:
                            events.append(self._event(
                                EventType.PERIMETER_EXIT,
                                observation,
                                zone.zone_id,
                                event_timestamp,
                            ))
                            state.first_inside_at = None
                            state.dwell_alerted = False
                    state.last_seen_at = timestamp
                    state.missing_since = None
                state.missing_since = None
                if (state.inside and state.first_inside_at is not None
                        and not state.dwell_alerted
                        and timestamp - state.first_inside_at >= self.dwell_threshold):
                    state.dwell_alerted = True
                    threshold_reached_at = (
                        state.first_inside_at + self.dwell_threshold
                    )
                    observation_gap_seconds = (
                        observation_gap if observation_gap is not None else 0.0
                    )
                    events.append(self._event(
                        EventType.DWELL_TIME_EXCEEDED, observation, zone.zone_id, timestamp,
                        {
                            "dwell_seconds": timestamp - state.first_inside_at,
                            "threshold_reached_at": threshold_reached_at,
                            "observation_gap_seconds": observation_gap_seconds,
                            "delayed_due_to_tracking_loss": (
                                observation_gap_seconds > 0
                            ),
                        },
                    ))

        for key, state in list(self._states.items()):
            if key not in seen:
                track_id = key[0]
                if lifecycle is not None:
                    if track_id in lifecycle.removed_ids:
                        del self._states[key]
                    elif track_id in lifecycle.tracked_ids or track_id in lifecycle.lost_ids:
                        if state.missing_since is None:
                            state.missing_since = timestamp
                    continue
                if state.missing_since is None:
                    state.missing_since = timestamp
                    state.candidate_inside = None
                    state.candidate_started_at = None
                    state.candidate_observations = 0
                elif timestamp - state.missing_since > self.loss_grace_period:
                    del self._states[key]
        return events

    def _transition_membership(self, state: TrackState, distance: float, timestamp: float):
        if state.inside:
            qualifies = distance < -self.hysteresis_margin
            target = False
            debounce = self.exit_debounce
        else:
            qualifies = distance > self.hysteresis_margin
            target = True
            debounce = self.entry_debounce
        if not qualifies:
            state.candidate_inside = None
            state.candidate_started_at = None
            state.candidate_observations = 0
            return None
        if state.candidate_inside != target:
            state.candidate_inside = target
            state.candidate_started_at = timestamp
            state.candidate_observations = 1
        else:
            state.candidate_observations += 1
        if (
            state.candidate_observations >= self.min_transition_observations
            and state.candidate_started_at is not None
            and timestamp - state.candidate_started_at >= debounce
        ):
            return target
        return None

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
