import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.config import (
    DEFAULT_MODEL_PATH,
    INFERENCE_SIZE,
    MODEL_PATH,
    resolve_inference_size,
    resolve_model_path,
)


class ModelConfigurationTests(unittest.TestCase):
    def test_default_model_path_is_custom_checkpoint_at_project_root(self):
        expected = Path(__file__).parents[1] / "runs" / "detect" / "models" / "thermal_perimeter_yolo11n-2" / "weights" / "best.pt"
        self.assertEqual(Path(MODEL_PATH), expected.resolve())
        self.assertEqual(Path(MODEL_PATH), DEFAULT_MODEL_PATH.resolve())
        self.assertNotEqual(Path(MODEL_PATH).name, "yolo11n.pt")

    def test_environment_override_is_resolved_from_project_root(self):
        with patch.dict(os.environ, {"THERMAL_MODEL_PATH": "custom/model.pt"}):
            self.assertEqual(
                Path(resolve_model_path()),
                (Path(__file__).parents[1] / "custom" / "model.pt").resolve(),
            )

    def test_absolute_environment_override_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            model_path = Path(temporary_directory) / "model.pt"
            with patch.dict(os.environ, {"THERMAL_MODEL_PATH": str(model_path)}):
                self.assertEqual(Path(resolve_model_path()), model_path.resolve())

    def test_default_inference_size_is_960(self):
        self.assertEqual(INFERENCE_SIZE, 960)
        self.assertEqual(resolve_inference_size(), 960)

    def test_environment_inference_size_overrides_work(self):
        with patch.dict(os.environ, {"THERMAL_INFERENCE_SIZE": "832"}):
            self.assertEqual(resolve_inference_size(), 832)
        with patch.dict(os.environ, {"THERMAL_INFERENCE_SIZE": "640"}):
            self.assertEqual(resolve_inference_size(), 640)

    def test_invalid_inference_size_is_rejected(self):
        for value in ("", "not-a-number", "0", "-1"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    resolve_inference_size(value)


if __name__ == "__main__":
    unittest.main()
