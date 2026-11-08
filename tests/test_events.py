import unittest

from scripts.inference.events import EventEngine, EventType
from scripts.inference.geofence import PolygonZone
from scripts.inference.models import TrackObservation


class EventEngineTests(unittest.TestCase):
    def setUp(self):
        self.zone = PolygonZone("z", ((0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)))

    def obs(self, track_id, x):
        return TrackObservation(track_id, 0, 0.9, (x, 20, x + 10, 80), (x + 5, 80))

    def update(self, engine, observations, timestamp):
        return engine.update(observations, [self.zone], (100, 100), timestamp)

    def test_first_observed_inside_is_not_entry(self):
        events = self.update(EventEngine(), [self.obs(1, 10)], 0)
        self.assertEqual([e.event_type for e in events], [EventType.FIRST_OBSERVED_INSIDE])

    def test_entry_exit_and_duplicate_prevention(self):
        engine = EventEngine()
        self.update(engine, [self.obs(1, 70)], 0)
        events = self.update(engine, [self.obs(1, 10)], 1)
        self.assertEqual([e.event_type for e in events], [EventType.PERIMETER_ENTRY])
        self.assertEqual(self.update(engine, [self.obs(1, 10)], 2), [])
        events = self.update(engine, [self.obs(1, 70)], 3)
        self.assertEqual([e.event_type for e in events], [EventType.PERIMETER_EXIT])

    def test_dwell_multiple_objects_and_track_loss(self):
        engine = EventEngine(dwell_threshold=3, loss_grace_period=2)
        self.update(engine, [self.obs(1, 10), self.obs(2, 10)], 0)
        self.assertEqual(self.update(engine, [self.obs(1, 10), self.obs(2, 10)], 3)[0].event_type,
                         EventType.DWELL_TIME_EXCEEDED)
        self.assertEqual(self.update(engine, [self.obs(1, 10), self.obs(2, 10)], 4), [])
        self.update(engine, [], 5)
        self.assertEqual(engine.state_count, 2)
        self.update(engine, [], 8)
        self.assertEqual(engine.state_count, 0)

    def test_tracking_loss_grace_preserves_dwell_state(self):
        engine = EventEngine(dwell_threshold=3, loss_grace_period=2)
        self.update(engine, [self.obs(1, 10)], 0)
        self.assertEqual(
            self.update(engine, [], 1), []
        )
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
        engine = EventEngine(loss_grace_period=0)
        self.update(engine, [self.obs(1, 10)], 0)
        self.update(engine, [], 1)
        self.update(engine, [], 2)
        events = self.update(engine, [self.obs(1, 70)], 3)
        self.assertEqual(events, [])
