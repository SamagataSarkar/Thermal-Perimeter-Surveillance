import time

from .annotator import FrameAnnotator
from .events import EventEngine
from .metrics import MetricsCollector
from .preprocessor import ThermalPreprocessor


class InferenceService:
    def __init__(self, detector, zones, dwell_threshold=3.0,
                 loss_grace_period=1.0, preprocessor=None,
                 entry_debounce=0.15, exit_debounce=0.25,
                 min_transition_observations=3, hysteresis_margin=4.0,
                 inference_size=960):
        self.detector = detector
        self.zones = list(zones)
        if not isinstance(inference_size, int) or inference_size <= 0:
            raise ValueError("inference_size must be a positive integer")
        self.inference_size = inference_size
        self.preprocessor = preprocessor or ThermalPreprocessor()
        self.events = EventEngine(
            dwell_threshold,
            loss_grace_period,
            entry_debounce,
            exit_debounce,
            min_transition_observations,
            hysteresis_margin,
        )
        self.annotator = FrameAnnotator()
        self.metrics = MetricsCollector()

    def process_packet(self, packet):
        started = time.monotonic()
        processed = self.preprocessor.process(packet.frame)
        result, observations = self.detector.process(
            processed, imgsz=self.inference_size
        )
        lifecycle = None
        tracker = getattr(self.detector, "tracker", None)
        lifecycle_snapshot = getattr(tracker, "lifecycle_snapshot", None)
        if lifecycle_snapshot is not None:
            lifecycle = lifecycle_snapshot()
        events = self.events.update(
            observations,
            self.zones,
            (processed.shape[1], processed.shape[0]),
            packet.timestamp,
            lifecycle,
        )
        annotated = self.annotator.annotate(
            processed, observations, self.zones, self.detector.class_names,
            [event.event_type for event in events],
        )
        self.metrics.record(started)
        return annotated, events, result

    def reset(self):
        self.detector.reset()
        self.events.reset()
        self.annotator.reset()
