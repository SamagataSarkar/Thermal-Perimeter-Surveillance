from typing import List

from .models import TrackObservation


class UltralyticsTracker:
    """Adapter around YOLO.track; Ultralytics remains the sole tracker."""

    def __init__(self, model, tracker_config: str):
        self.model = model
        self.tracker_config = tracker_config

    def track(self, frame, confidence=0.30, iou=0.5):
        results = self.model.track(
            frame,
            persist=True,
            tracker=self.tracker_config,
            conf=confidence,
            iou=iou,
            verbose=False,
        )
        return results[0]

    def reset(self):
        predictor = getattr(self.model, "predictor", None)
        if predictor is not None:
            predictor.trackers = []
            predictor.vid_path = []
            predictor._feats = None

    @staticmethod
    def observations(result) -> List[TrackObservation]:
        boxes = result.boxes
        if boxes is None or boxes.id is None:
            return []
        xyxy = boxes.xyxy.cpu().numpy()
        ids = boxes.id.int().cpu().tolist()
        classes = boxes.cls.int().cpu().tolist()
        confidence = boxes.conf.cpu().numpy()
        observations = []
        for box, track_id, class_id, conf in zip(xyxy, ids, classes, confidence):
            x1, y1, x2, y2 = map(int, box)
            observations.append(TrackObservation(
                track_id=track_id,
                class_id=class_id,
                confidence=float(conf),
                box=(x1, y1, x2, y2),
                point=((x1 + x2) // 2, y2),
            ))
        return observations
