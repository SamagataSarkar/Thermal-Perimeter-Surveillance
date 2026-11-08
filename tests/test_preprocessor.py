import unittest
from unittest.mock import patch

import cv2
import numpy as np

from scripts.inference.preprocessor import ThermalPreprocessor


class ThermalPreprocessorTests(unittest.TestCase):
    def test_clahe_is_initialized_once(self):
        with patch("scripts.inference.preprocessor.cv2.createCLAHE") as create_clahe:
            clahe = create_clahe.return_value
            clahe.apply.return_value = np.zeros((4, 6), dtype=np.uint8)
            preprocessor = ThermalPreprocessor(clip_limit=3.0, tile_grid_size=(4, 4))

            frame = np.zeros((4, 6, 3), dtype=np.uint8)
            preprocessor.process(frame)
            preprocessor.process(frame)

            create_clahe.assert_called_once_with(clipLimit=3.0, tileGridSize=(4, 4))
            self.assertEqual(clahe.apply.call_count, 2)

    def test_output_preserves_frame_shape_and_bgr_channels(self):
        preprocessor = ThermalPreprocessor()
        frame = np.zeros((12, 16, 3), dtype=np.uint8)

        processed = preprocessor.process(frame)

        self.assertEqual(processed.shape, frame.shape)
        self.assertEqual(processed.dtype, np.uint8)


if __name__ == "__main__":
    unittest.main()
