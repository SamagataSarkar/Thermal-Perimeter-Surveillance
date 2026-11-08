import math
from collections import defaultdict

import cv2
import numpy as np

from .geofence import PolygonZone


class FrameAnnotator:
    def __init__(self):
        self.history = defaultdict(list)

    def annotate(self, frame, observations, zones, class_names, event_types=()):
        for zone in zones:
            polygon = zone.points_for_frame(frame.shape[1], frame.shape[0])
            overlay = frame.copy()
            cv2.fillPoly(overlay, [polygon], (0, 50, 120))
            cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
            cv2.polylines(frame, [polygon], True, (0, 255, 255), 2)
        for observation in observations:
            history = self.history[observation.track_id]
            history.append(observation.point)
            del history[:-25]
            if len(history) > 1:
                points = np.asarray(history, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [points], False, (0, 255, 0), 2)
            x1, y1, x2, y2 = observation.box
            width, height = x2 - x1, y2 - y1
            labels = []
            if observation.class_id == 3 and len(history) >= 20:
                displacement = math.hypot(
                    history[-1][0] - history[0][0], history[-1][1] - history[0][1]
                )
                if displacement < 15.0:
                    labels.append("LOW_MOTION_CANDIDATE")
            if observation.class_id == 0 and height > 0 and width / height > 1.2:
                labels.append("HORIZONTAL_POSTURE_CANDIDATE")
            name = class_names.get(observation.class_id, "cls_{}".format(observation.class_id))
            label = "ID {} | {} {:.2f}".format(observation.track_id, name, observation.confidence)
            if labels:
                label += " | " + ", ".join(labels)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, label, (x1, max(25, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 2)
        return frame

    def reset(self):
        self.history.clear()
