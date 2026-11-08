import unittest

from scripts.inference.geofence import PolygonZone


class GeofenceTests(unittest.TestCase):
    def setUp(self):
        self.zone = PolygonZone("z", ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))

    def test_polygon_membership_and_normalization(self):
        self.assertTrue(self.zone.contains((50, 50), 100, 100))
        self.assertFalse(self.zone.contains((150, 50), 100, 100))
        self.assertEqual(self.zone.points_for_frame(200, 100)[2, 0].tolist(), [200, 100])

    def test_invalid_polygon(self):
        with self.assertRaises(ValueError):
            PolygonZone("bad", ((0.0, 0.0), (1.2, 0.0), (1.0, 1.0)))
