import threading
import unittest
from unittest.mock import Mock, patch

import numpy as np

from scripts.inference.video_source import RecordedVideoSource, ThreadedLiveSource


class FakeCapture:
    def __init__(self, frames, fps=10.0, opened=True):
        self.frames = list(frames)
        self.fps = fps
        self.opened = opened
        self.released = False

    def isOpened(self):
        return self.opened

    def get(self, property_id):
        return self.fps

    def read(self):
        if self.frames:
            return True, self.frames.pop(0)
        return False, None

    def release(self):
        self.released = True


class VideoSourceTests(unittest.TestCase):
    def test_recorded_video_lifecycle_and_source_timestamps(self):
        frames = [
            np.zeros((2, 3, 3), dtype=np.uint8),
            np.ones((2, 3, 3), dtype=np.uint8),
        ]
        capture = FakeCapture(frames, fps=10.0)
        with patch("scripts.inference.video_source.cv2.VideoCapture", return_value=capture):
            source = RecordedVideoSource("recorded.mp4")
            with source:
                first = source.read()
                second = source.read()
                self.assertAlmostEqual(first.timestamp, 0.0)
                self.assertAlmostEqual(second.timestamp, 0.1)
                self.assertEqual(first.frame_index, 0)
                self.assertEqual(second.frame_index, 1)
                self.assertIsNone(source.read())
            self.assertTrue(capture.released)

    def test_live_source_uses_monotonic_capture_timestamp(self):
        capture = FakeCapture(
            [np.zeros((2, 3, 3), dtype=np.uint8)],
            fps=30.0,
        )
        with patch("scripts.inference.video_source.cv2.VideoCapture", return_value=capture):
            with patch(
                "scripts.inference.video_source.time.monotonic",
                side_effect=[42.5, 42.6],
            ):
                source = ThreadedLiveSource("rtsp://camera", queue_size=1)
                source.start()
                packet = source.read(timeout=1.0)
                source.close()

        self.assertIsNotNone(packet)
        self.assertEqual(packet.timestamp, 42.5)
        self.assertTrue(capture.released)

    def test_live_source_reports_capture_failure_and_shuts_down(self):
        capture = FakeCapture([], opened=True)
        with patch("scripts.inference.video_source.cv2.VideoCapture", return_value=capture):
            source = ThreadedLiveSource("rtsp://camera")
            source.start()
            with self.assertRaises(RuntimeError):
                source.read(timeout=1.0)
            source.close()

        self.assertTrue(source.stop_event.is_set())
        self.assertTrue(capture.released)

    def test_live_source_rejects_failed_connection(self):
        capture = FakeCapture([], opened=False)
        with patch("scripts.inference.video_source.cv2.VideoCapture", return_value=capture):
            with self.assertRaises(RuntimeError):
                ThreadedLiveSource("rtsp://missing").start()


if __name__ == "__main__":
    unittest.main()
