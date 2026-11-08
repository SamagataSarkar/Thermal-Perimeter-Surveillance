import time

from .annotator import FrameAnnotator
from .events import EventEngine
from .metrics import MetricsCollector
from .preprocessor import ThermalPreprocessor


class InferenceService:
    def __init__(self, detector, zones, dwell_threshold=3.0,
                 loss_grace_period=1.0, preprocessor=None):
        self.detector = detector
        self.zones = list(zones)
        self.preprocessor = preprocessor or ThermalPreprocessor()
        self.events = EventEngine(dwell_threshold, loss_grace_period)
        self.annotator = FrameAnnotator()
        self.metrics = MetricsCollector()

    def process_packet(self, packet):
        started = time.monotonic()
        processed = self.preprocessor.process(packet.frame)
        result, observations = self.detector.process(processed)
        events = self.events.update(
            observations, self.zones, (processed.shape[1], processed.shape[0]), packet.timestamp
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
