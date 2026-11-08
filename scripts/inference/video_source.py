import threading
import time
from queue import Empty, Full, Queue

import cv2

from .models import FramePacket


class RecordedVideoSource:
    def __init__(self, source):
        self.source = source
        self.capture = None
        self.index = 0
        self.fps = 0.0

    def __enter__(self):
        self.capture = cv2.VideoCapture(self.source)
        if not self.capture.isOpened():
            raise RuntimeError("Unable to open recorded video: {}".format(self.source))
        self.fps = self.capture.get(cv2.CAP_PROP_FPS) or 0.0
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def read(self):
        ret, frame = self.capture.read()
        if not ret:
            return None
        timestamp = self.index / self.fps if self.fps > 0 else float(self.index)
        packet = FramePacket(frame, timestamp, self.index)
        self.index += 1
        return packet

    def close(self):
        if self.capture is not None:
            self.capture.release()


class ThreadedLiveSource:
    def __init__(self, source=0, queue_size=1):
        if queue_size < 1:
            raise ValueError("queue_size must be positive")
        self.source = source
        self.queue = Queue(maxsize=queue_size)
        self.stop_event = threading.Event()
        self.thread = None
        self.capture = None
        self.error = None
        self.index = 0

    def start(self):
        self.capture = cv2.VideoCapture(self.source)
        if not self.capture.isOpened():
            raise RuntimeError("Unable to open live video source: {}".format(self.source))
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        return self

    def _update(self):
        try:
            while not self.stop_event.is_set():
                ret, frame = self.capture.read()
                if not ret:
                    self.error = RuntimeError("Live video source stopped returning frames")
                    break
                packet = FramePacket(frame, time.monotonic(), self.index)
                self.index += 1
                try:
                    self.queue.put_nowait(packet)
                except Full:
                    try:
                        self.queue.get_nowait()
                    except Empty:
                        pass
                    self.queue.put_nowait(packet)
        except Exception as exc:
            self.error = exc

    def read(self, timeout=1.0):
        if self.error is not None and self.queue.empty():
            raise self.error
        try:
            return self.queue.get(timeout=timeout)
        except Empty:
            return None

    def close(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        if self.capture is not None:
            self.capture.release()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
