import time
from dataclasses import dataclass


@dataclass
class Metrics:
    fps: float = 0.0
    inference_latency_ms: float = 0.0
    frames: int = 0


class MetricsCollector:
    def __init__(self):
        self.metrics = Metrics()
        self._last_frame_at = None

    def record(self, started_at):
        now = time.monotonic()
        if self._last_frame_at is not None and now > self._last_frame_at:
            self.metrics.fps = 1.0 / (now - self._last_frame_at)
        self._last_frame_at = now
        self.metrics.inference_latency_ms = (now - started_at) * 1000.0
        self.metrics.frames += 1
