from ultralytics import YOLO

from .tracker import UltralyticsTracker


class Detector:
    def __init__(self, model_path: str, tracker_config: str):
        self.model = YOLO(model_path)
        self.tracker = UltralyticsTracker(self.model, tracker_config)

    def process(self, frame, confidence=0.30, iou=0.5, imgsz=960):
        result = self.tracker.track(frame, confidence, iou, imgsz=imgsz)
        return result, self.tracker.observations(result)

    def reset(self):
        self.tracker.reset()

    @property
    def class_names(self):
        return self.model.names
