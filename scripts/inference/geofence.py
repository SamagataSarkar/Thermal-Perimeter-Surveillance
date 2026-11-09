from dataclasses import dataclass
from typing import Iterable, List, Tuple

import cv2
import numpy as np

from .models import Point


@dataclass(frozen=True)
class PolygonZone:
    zone_id: str
    normalized_points: Tuple[Tuple[float, float], ...]

    def __post_init__(self):
        if len(self.normalized_points) < 3:
            raise ValueError("A polygon zone requires at least three points")
        if any(not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0)
               for x, y in self.normalized_points):
            raise ValueError("Polygon points must be normalized to [0, 1]")

    def points_for_frame(self, width: int, height: int) -> np.ndarray:
        points = [(round(x * width), round(y * height))
                  for x, y in self.normalized_points]
        return np.asarray(points, dtype=np.int32).reshape((-1, 1, 2))

    def contains(self, point: Point, width: int, height: int) -> bool:
        polygon = self.points_for_frame(width, height)
        return cv2.pointPolygonTest(polygon, point, False) >= 0

    def signed_distance(self, point: Point, width: int, height: int) -> float:
        polygon = self.points_for_frame(width, height)
        return float(cv2.pointPolygonTest(polygon, point, True))

    def draw(self, frame, color=(0, 255, 255), thickness=2):
        height, width = frame.shape[:2]
        polygon = self.points_for_frame(width, height)
        cv2.polylines(frame, [polygon], True, color, thickness)
        return polygon


def default_perimeter_zone() -> PolygonZone:
    return PolygonZone(
        "perimeter",
        ((0.25, 0.50), (0.75, 0.50), (1.0, 1.0), (0.0, 1.0)),
    )
