import unittest

from pydantic import ValidationError

from backend.app.db.models import SourceType, VideoSource
from backend.app.schemas.geofences import GeofenceCreate
from backend.app.schemas.video_sources import VideoSourceCreate, VideoSourceRead, redact_source_uri


class ApiSchemaTests(unittest.TestCase):
    def test_encoded_rtsp_credentials_are_redacted(self):
        uri = "rtsp://user%40name:p%40ss%3Aword@camera.local:554/live"
        redacted = redact_source_uri(uri)
        self.assertNotIn("user", redacted)
        self.assertNotIn("p%40ss", redacted)
        self.assertNotIn("user%40name:", redacted)
        self.assertIn("camera.local", redacted)
        response = VideoSourceRead.model_validate(VideoSource(
            id=1, name="Camera", source_type=SourceType.RTSP, source_uri=uri, enabled=True
        ))
        self.assertNotIn("user", response.model_dump_json())
        self.assertNotIn("p%40ss", response.model_dump_json())

    def test_file_uri_is_not_changed(self):
        self.assertEqual(redact_source_uri("demo_thermal2.mp4"), "demo_thermal2.mp4")

    def test_schema_validates_source_and_polygon(self):
        source = VideoSourceCreate(name="Camera", source_type="RTSP", source_uri="rtsp://camera/live")
        self.assertEqual(source.source_type, "RTSP")
        with self.assertRaises(ValidationError):
            GeofenceCreate(name="Bad", normalized_polygon=[[0, 0], [1.1, 0], [1, 1]])


if __name__ == "__main__":
    unittest.main()
