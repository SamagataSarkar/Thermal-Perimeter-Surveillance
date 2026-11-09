import unittest

from scripts.inference.events import EventEngine, EventType
from scripts.inference.geofence import PolygonZone
from scripts.inference.models import TrackObservation, TrackerLifecycle


class EventEngineTests(unittest.TestCase):
    def setUp(self):
        self.zone = PolygonZone("z", ((0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)))

    def obs(self, track_id, x):
        return TrackObservation(track_id, 0, 0.9, (x, 20, x + 10, 80), (x + 5, 80))

    def update(self, engine, observations, timestamp):
        return engine.update(observations, [self.zone], (100, 100), timestamp)

    def update_with_lifecycle(self, engine, observations, timestamp, tracked=(),
                              lost=(), removed=()):
        lifecycle = TrackerLifecycle(frozenset(tracked), frozenset(lost),
                                     frozenset(removed))
        return engine.update(
            observations, [self.zone], (100, 100), timestamp, lifecycle
        )

    def test_first_observed_inside_is_not_entry(self):
        events = self.update(EventEngine(), [self.obs(1, 10)], 0)
        self.assertEqual([e.event_type for e in events], [EventType.FIRST_OBSERVED_INSIDE])

    def test_entry_exit_and_duplicate_prevention(self):
        engine = EventEngine(entry_debounce=0, exit_debounce=0,
                             min_transition_observations=1, hysteresis_margin=0)
        self.update(engine, [self.obs(1, 70)], 0)
        events = self.update(engine, [self.obs(1, 10)], 1)
        self.assertEqual([e.event_type for e in events], [EventType.PERIMETER_ENTRY])
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 2), [])
        events = self.update(engine, [self.obs(1, 70)], 3)
        self.assertEqual([e.event_type for e in events], [EventType.PERIMETER_EXIT])

    def test_dwell_multiple_objects_and_track_loss(self):
        engine = EventEngine(dwell_threshold=3, loss_grace_period=2,
                             entry_debounce=0, exit_debounce=0,
                             min_transition_observations=1, hysteresis_margin=0)
        self.update(engine, [self.obs(1, 10), self.obs(2, 10)], 0)
        self.assertEqual(self.update(engine, [self.obs(1, 10), self.obs(2, 10)], 3)[0].event_type,
                         EventType.DWELL_TIME_EXCEEDED)
        self.assertEqual(self.update(engine, [self.obs(1, 10), self.obs(2, 10)], 4), [])
        self.update(engine, [], 5)
        self.assertEqual(engine.state_count, 2)
        self.update(engine, [], 8)
        self.assertEqual(engine.state_count, 0)

    def test_tracking_loss_grace_preserves_dwell_state(self):
        engine = EventEngine(dwell_threshold=3, loss_grace_period=2,
                             entry_debounce=0, exit_debounce=0,
                             min_transition_observations=1, hysteresis_margin=0)
        self.update(engine, [self.obs(1, 10)], 0)
        self.update(engine, [self.obs(1, 10)], 1)
        self.assertEqual(self.update(engine, [], 2), [])
        events = self.update(engine, [self.obs(1, 10)], 3)
        self.assertEqual([event.event_type for event in events],
                         [EventType.DWELL_TIME_EXCEEDED])

    def test_multiple_zones_are_independent(self):
        second_zone = PolygonZone(
            "z2", ((0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0))
        )
        engine = EventEngine()
        events = engine.update([self.obs(1, 10)], [self.zone, second_zone], (100, 100), 0)
        self.assertEqual([event.zone_id for event in events], ["z"])

    def test_id_reuse_starts_new_state_after_cleanup(self):
        engine = EventEngine(loss_grace_period=0, entry_debounce=0,
                             exit_debounce=0, min_transition_observations=1,
                             hysteresis_margin=0)
        self.update(engine, [self.obs(1, 10)], 0)
        self.update(engine, [], 2)
        self.update(engine, [], 3)
        events = self.update(engine, [self.obs(1, 70)], 3)
        self.assertEqual(events, [])

    def test_sustained_crossings_use_debounce_and_candidate_timestamp(self):
        engine = EventEngine(entry_debounce=0.15, exit_debounce=0.25,
                             min_transition_observations=3, hysteresis_margin=4)
        self.update(engine, [self.obs(1, 70)], 0.0)
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 1.0), [])
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 1.1), [])
        events = self.update(engine, [self.obs(1, 10)], 1.2)
        self.assertEqual([event.event_type for event in events],
                         [EventType.PERIMETER_ENTRY])
        self.assertEqual(events[0].timestamp, 1.0)

        self.assertEqual(self.update(engine, [self.obs(1, 70)], 2.0), [])
        self.assertEqual(self.update(engine, [self.obs(1, 70)], 2.1), [])
        events = self.update(engine, [self.obs(1, 70)], 2.3)
        self.assertEqual([event.event_type for event in events],
                         [EventType.PERIMETER_EXIT])
        self.assertEqual(events[0].timestamp, 2.0)

    def test_rapid_jitter_is_suppressed_and_pending_transition_can_cancel(self):
        engine = EventEngine(entry_debounce=0.15, exit_debounce=0.25,
                             min_transition_observations=3, hysteresis_margin=4)
        self.update(engine, [self.obs(1, 70)], 0.0)
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 1.0), [])
        self.assertEqual(self.update(engine, [self.obs(1, 70)], 1.1), [])
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 1.2), [])
        self.assertEqual(self.update(engine, [self.obs(1, 70)], 1.3), [])

    def test_hysteresis_neutral_band_preserves_membership(self):
        engine = EventEngine(entry_debounce=0, exit_debounce=0,
                             min_transition_observations=1, hysteresis_margin=4)
        self.update(engine, [self.obs(1, 70)], 0.0)
        self.assertEqual(self.update(engine, [self.obs(1, 47)], 1.0), [])
        self.assertEqual(self.update(engine, [self.obs(1, 47)], 2.0), [])
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 3.0)[0].event_type,
                         EventType.PERIMETER_ENTRY)

    def test_dwell_is_once_per_visit_and_restarts_after_confirmed_entry(self):
        engine = EventEngine(dwell_threshold=3, entry_debounce=0.15,
                             exit_debounce=0.25, min_transition_observations=3,
                             hysteresis_margin=4)
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 0.0)[0].event_type,
                         EventType.FIRST_OBSERVED_INSIDE)
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 3.0)[0].event_type,
                         EventType.DWELL_TIME_EXCEEDED)
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 4.0), [])

        self.update(engine, [self.obs(1, 70)], 5.0)
        self.update(engine, [self.obs(1, 70)], 5.1)
        self.assertEqual(self.update(engine, [self.obs(1, 70)], 5.3)[0].event_type,
                         EventType.PERIMETER_EXIT)
        self.update(engine, [self.obs(1, 10)], 6.0)
        self.update(engine, [self.obs(1, 10)], 6.1)
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 6.2)[0].event_type,
                         EventType.PERIMETER_ENTRY)
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 9.3)[0].event_type,
                         EventType.DWELL_TIME_EXCEEDED)
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 10.0), [])

    def test_recorded_video_timestamps_drive_debounce_and_dwell(self):
        engine = EventEngine(dwell_threshold=3, entry_debounce=0.15,
                             exit_debounce=0.25, min_transition_observations=3,
                             hysteresis_margin=4)
        self.update(engine, [self.obs(1, 70)], 0.0)
        self.update(engine, [self.obs(1, 10)], 10.0)
        self.update(engine, [self.obs(1, 10)], 10.05)
        events = self.update(engine, [self.obs(1, 10)], 10.2)
        self.assertEqual(events[0].timestamp, 10.0)
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 13.2)[0].event_type,
                         EventType.DWELL_TIME_EXCEEDED)

    def test_dwell_details_distinguish_threshold_and_emission_times(self):
        engine = EventEngine(dwell_threshold=3, entry_debounce=0,
                             exit_debounce=0, min_transition_observations=1,
                             hysteresis_margin=0)
        self.update(engine, [self.obs(1, 10)], 0)
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 3)[0].details, {
            "dwell_seconds": 3,
            "threshold_reached_at": 3,
            "observation_gap_seconds": 0.0,
            "delayed_due_to_tracking_loss": False,
        })

    def test_dwell_crossed_during_short_lifecycle_loss_emits_on_recovery(self):
        engine = EventEngine(dwell_threshold=3, loss_grace_period=1,
                             entry_debounce=0, exit_debounce=0,
                             min_transition_observations=1, hysteresis_margin=0)
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 0, tracked=(1,))
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 2, tracked=(1,))
        self.update_with_lifecycle(engine, [], 2, lost=(1,))
        events = self.update_with_lifecycle(engine, [self.obs(1, 10)], 3,
                                            tracked=(1,))
        self.assertEqual(events[0].event_type, EventType.DWELL_TIME_EXCEEDED)
        self.assertEqual(events[0].timestamp, 3)
        self.assertEqual(events[0].details["threshold_reached_at"], 3)
        self.assertEqual(events[0].details["observation_gap_seconds"], 1)
        self.assertTrue(events[0].details["delayed_due_to_tracking_loss"])
        self.assertEqual(self.update_with_lifecycle(
            engine, [self.obs(1, 10)], 4, tracked=(1,)
        ), [])

    def test_long_recovery_gap_restarts_dwell_without_first_observed(self):
        engine = EventEngine(dwell_threshold=3, loss_grace_period=1,
                             entry_debounce=0, exit_debounce=0,
                             min_transition_observations=1, hysteresis_margin=0)
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 0, tracked=(1,))
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 1, tracked=(1,))
        self.update_with_lifecycle(engine, [], 2, lost=(1,))
        self.assertEqual(self.update_with_lifecycle(
            engine, [self.obs(1, 10)], 3, tracked=(1,)
        ), [])
        self.assertEqual(self.update_with_lifecycle(
            engine, [self.obs(1, 10)], 6, tracked=(1,)
        )[0].event_type, EventType.DWELL_TIME_EXCEEDED)

    def test_long_recovery_after_dwell_does_not_emit_second_dwell(self):
        engine = EventEngine(dwell_threshold=3, loss_grace_period=1,
                             entry_debounce=0, exit_debounce=0,
                             min_transition_observations=1, hysteresis_margin=0)
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 0, tracked=(1,))
        self.assertEqual(self.update_with_lifecycle(
            engine, [self.obs(1, 10)], 3, tracked=(1,)
        )[0].event_type, EventType.DWELL_TIME_EXCEEDED)
        self.update_with_lifecycle(engine, [], 4, lost=(1,))
        self.assertEqual(self.update_with_lifecycle(
            engine, [self.obs(1, 10)], 6, tracked=(1,)
        ), [])
        self.assertEqual(self.update_with_lifecycle(
            engine, [self.obs(1, 10)], 9, tracked=(1,)
        ), [])

    def test_recovery_at_grace_boundary_preserves_dwell_and_no_duplicate_first(self):
        engine = EventEngine(dwell_threshold=3, loss_grace_period=1,
                             entry_debounce=0, exit_debounce=0,
                             min_transition_observations=1, hysteresis_margin=0)
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 0, tracked=(1,))
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 2, tracked=(1,))
        self.update_with_lifecycle(engine, [], 2, lost=(1,))
        events = self.update_with_lifecycle(engine, [self.obs(1, 10)], 3,
                                            tracked=(1,))
        self.assertEqual([event.event_type for event in events],
                         [EventType.DWELL_TIME_EXCEEDED])

    def test_removed_track_discards_pending_dwell(self):
        engine = EventEngine(dwell_threshold=3, entry_debounce=0,
                             exit_debounce=0, min_transition_observations=1,
                             hysteresis_margin=0)
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 0, tracked=(1,))
        self.update_with_lifecycle(engine, [], 1, lost=(1,))
        self.update_with_lifecycle(engine, [], 2, removed=(1,))
        self.assertEqual(engine.state_count, 0)

    def test_lost_track_in_tracker_pool_preserves_state(self):
        engine = EventEngine(dwell_threshold=3, entry_debounce=0,
                             exit_debounce=0, min_transition_observations=1,
                             hysteresis_margin=0)
        self.assertEqual(
            self.update_with_lifecycle(engine, [self.obs(1, 10)], 0, tracked=(1,))[0].event_type,
            EventType.FIRST_OBSERVED_INSIDE,
        )
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 2, tracked=(1,))
        self.assertEqual(self.update_with_lifecycle(
            engine, [], 2, lost=(1,)
        ), [])
        self.assertEqual(
            self.update_with_lifecycle(engine, [self.obs(1, 10)], 3, tracked=(1,))[0].event_type,
            EventType.DWELL_TIME_EXCEEDED,
        )

    def test_recovery_does_not_generate_first_observed_inside_again(self):
        engine = EventEngine(entry_debounce=0, exit_debounce=0,
                             min_transition_observations=1, hysteresis_margin=0)
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 0, tracked=(1,))
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 2, tracked=(1,))
        self.assertEqual(self.update_with_lifecycle(
            engine, [], 2, lost=(1,)
        ), [])
        events = self.update_with_lifecycle(
            engine, [self.obs(1, 10)], 3, tracked=(1,)
        )
        self.assertEqual([event.event_type for event in events],
                         [EventType.DWELL_TIME_EXCEEDED])

    def test_lost_track_beyond_grace_period_is_retained_until_removed(self):
        engine = EventEngine(loss_grace_period=1, entry_debounce=0,
                             exit_debounce=0, min_transition_observations=1,
                             hysteresis_margin=0)
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 0, tracked=(1,))
        self.update_with_lifecycle(engine, [], 2, lost=(1,))
        self.assertEqual(engine.state_count, 1)
        self.update_with_lifecycle(engine, [], 90, removed=(1,))
        self.assertEqual(engine.state_count, 0)

    def test_removed_track_cleans_all_zone_state(self):
        second_zone = PolygonZone(
            "z2", ((0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0))
        )
        engine = EventEngine(entry_debounce=0, exit_debounce=0,
                             min_transition_observations=1, hysteresis_margin=0)
        engine.update([self.obs(1, 10)], [self.zone, second_zone], (100, 100), 0,
                      TrackerLifecycle(frozenset({1}), frozenset(), frozenset()))
        self.assertEqual(engine.state_count, 2)
        engine.update([], [self.zone, second_zone], (100, 100), 1,
                      TrackerLifecycle(frozenset(), frozenset(), frozenset({1})))
        self.assertEqual(engine.state_count, 0)

    def test_recovery_supports_confirmed_exit_and_later_entry(self):
        engine = EventEngine(entry_debounce=0, exit_debounce=0,
                             min_transition_observations=1, hysteresis_margin=0)
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 0, tracked=(1,))
        self.update_with_lifecycle(engine, [], 1, lost=(1,))
        self.assertEqual(
            self.update_with_lifecycle(engine, [self.obs(1, 70)], 2, tracked=(1,))[0].event_type,
            EventType.PERIMETER_EXIT,
        )
        self.assertEqual(
            self.update_with_lifecycle(engine, [self.obs(1, 10)], 3, tracked=(1,))[0].event_type,
            EventType.PERIMETER_ENTRY,
        )

    def test_lifecycle_and_zone_state_are_independent(self):
        second_zone = PolygonZone(
            "z2", ((0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0))
        )
        engine = EventEngine(entry_debounce=0, exit_debounce=0,
                             min_transition_observations=1, hysteresis_margin=0)
        lifecycle = TrackerLifecycle(frozenset({1, 2}), frozenset(), frozenset())
        events = engine.update(
            [self.obs(1, 10), self.obs(2, 70)],
            [self.zone, second_zone],
            (100, 100),
            0,
            lifecycle,
        )
        self.assertEqual(
            {(event.track_id, event.zone_id) for event in events},
            {(1, "z"), (2, "z2")},
        )
        engine.update(
            [], [self.zone, second_zone], (100, 100), 1,
            TrackerLifecycle(frozenset({1}), frozenset({2}), frozenset()),
        )
        self.assertEqual(engine.state_count, 4)
        engine.update(
            [], [self.zone, second_zone], (100, 100), 2,
            TrackerLifecycle(frozenset({1}), frozenset(), frozenset({2})),
        )
        self.assertEqual(engine.state_count, 2)

    def test_lifecycle_fallback_preserves_existing_timeout_behavior(self):
        engine = EventEngine(loss_grace_period=1, entry_debounce=0,
                             exit_debounce=0, min_transition_observations=1,
                             hysteresis_margin=0)
        self.update(engine, [self.obs(1, 10)], 0)
        self.update(engine, [], 2)
        self.assertEqual(engine.state_count, 1)
        self.update(engine, [], 4)
        self.assertEqual(engine.state_count, 0)

    def test_reset_clears_lifecycle_managed_event_state(self):
        engine = EventEngine()
        self.update_with_lifecycle(engine, [self.obs(1, 10)], 0, tracked=(1,))
        self.assertEqual(engine.state_count, 1)
        engine.reset()
        self.assertEqual(engine.state_count, 0)
