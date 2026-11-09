import unittest
from types import SimpleNamespace

from scripts.inference.models import TrackerLifecycle
from scripts.inference.tracker import ClassAwareByteTracker, UltralyticsTracker


class FakeTrack:
    def __init__(self, track_id):
        self.track_id = track_id


class FakeCandidate:
    def __init__(self, class_id, score):
        self.cls = class_id
        self.score = score
        self.activated = False

    def activate(self, kalman_filter, frame_id):
        self.activated = True


class FakeModel:
    class Predictor:
        trackers = []

    def __init__(self, trackers):
        self.predictor = self.Predictor()
        self.predictor.trackers = trackers
        self.callbacks = {
            "on_predict_start": [],
            "on_predict_postprocess_end": [],
        }

    def add_callback(self, event, callback):
        self.callbacks[event].append(callback)


class TrackingModel(FakeModel):
    def __init__(self):
        super().__init__([])
        self.calls = []

    def predict(self, source, **kwargs):
        self.calls.append(kwargs)
        return [type("Result", (), {})()]


class TrackerLifecycleTests(unittest.TestCase):
    def test_snapshot_reads_post_update_tracker_pools(self):
        tracker = type("Tracker", (), {
            "tracked_stracks": [FakeTrack(1), FakeTrack(2)],
            "lost_stracks": [FakeTrack(3)],
            "removed_stracks_frame": [FakeTrack(4)],
        })()
        wrapper = UltralyticsTracker(FakeModel([tracker]), "custom_tracker.yaml")
        self.assertEqual(
            wrapper._read_lifecycle(),
            TrackerLifecycle(frozenset({1, 2}), frozenset({3}), frozenset({4})),
        )

    def test_snapshot_is_unavailable_without_predictor_trackers(self):
        wrapper = UltralyticsTracker(FakeModel([]), "custom_tracker.yaml")
        self.assertIsNone(wrapper._read_lifecycle())

    def test_configured_inference_size_reaches_ultralytics_track(self):
        model = TrackingModel()
        wrapper = UltralyticsTracker(model, "custom_tracker.yaml")
        wrapper.track("frame", confidence=0.30, iou=0.5, imgsz=832)
        self.assertEqual(model.calls[0]["imgsz"], 832)
        self.assertEqual(model.calls[0]["conf"], 0.30)
        self.assertEqual(model.calls[0]["iou"], 0.5)

    def test_person_new_track_threshold_is_class_specific(self):
        tracker = ClassAwareByteTracker.__new__(ClassAwareByteTracker)
        tracker.args = SimpleNamespace(new_track_thresh=0.40)
        tracker.kalman_filter = object()
        tracker.frame_id = 1
        person_low = FakeCandidate(0, 0.45)
        person_high = FakeCandidate(0, 0.63)
        vehicle = FakeCandidate(1, 0.40)
        activated = []
        tracker._init_new_tracks(
            [0, 1, 2], [person_low, person_high, vehicle], activated
        )
        self.assertFalse(person_low.activated)
        self.assertTrue(person_high.activated)
        self.assertTrue(vehicle.activated)


if __name__ == "__main__":
    unittest.main()
