from functools import partial
from typing import List, Optional

from ultralytics.trackers.byte_tracker import BYTETracker
from ultralytics.trackers.track import on_predict_start, register_tracker

from .models import TrackObservation, TrackerLifecycle


class ClassAwareByteTracker(BYTETracker):
    """Keep normal ByteTrack association while gating only new person tracks."""

    person_new_track_threshold = 0.50

    def _init_new_tracks(
        self, u_detection, detections, activated, refind=None
    ) -> None:
        for inew in u_detection:
            track = detections[inew]
            threshold = self.args.new_track_thresh
            if getattr(track, "cls", None) is not None and int(track.cls) == 0:
                threshold = self.person_new_track_threshold
            if track.score < threshold:
                continue
            track.activate(self.kalman_filter, self.frame_id)
            activated.append(track)


def _on_predict_start_class_aware(predictor, persist=False):
    on_predict_start(predictor, persist=persist)
    trackers = []
    for tracker in predictor.trackers:
        if isinstance(tracker, ClassAwareByteTracker):
            trackers.append(tracker)
            continue
        replacement = ClassAwareByteTracker(args=tracker.args)
        trackers.append(replacement)
    predictor.trackers = trackers


class UltralyticsTracker:
    """Adapter around YOLO.track; Ultralytics remains the sole tracker."""

    def __init__(self, model, tracker_config: str):
        self.model = model
        self.tracker_config = tracker_config
        self._lifecycle: Optional[TrackerLifecycle] = None

    def track(self, frame, confidence=0.30, iou=0.5, imgsz=960):
        register_tracker(self.model, persist=True)
        self._install_class_aware_start_callback()
        results = self.model.predict(
            source=frame,
            tracker=self.tracker_config,
            conf=confidence,
            iou=iou,
            imgsz=imgsz,
            batch=1,
            mode="track",
            verbose=False,
        )
        result = results[0]
        self._lifecycle = self._read_lifecycle()
        return result

    def _install_class_aware_start_callback(self) -> None:
        callbacks = self.model.callbacks["on_predict_start"]
        callbacks[:] = [
            callback for callback in callbacks
            if getattr(callback, "func", None) is not on_predict_start
        ]
        if not any(
            getattr(callback, "func", None) is _on_predict_start_class_aware
            for callback in callbacks
        ):
            callbacks.append(partial(_on_predict_start_class_aware, persist=True))

    def lifecycle_snapshot(self) -> Optional[TrackerLifecycle]:
        return self._lifecycle

    def _read_lifecycle(self) -> Optional[TrackerLifecycle]:
        predictor = getattr(self.model, "predictor", None)
        trackers = getattr(predictor, "trackers", None)
        if not trackers:
            return None
        tracked_ids = set()
        lost_ids = set()
        removed_ids = set()
        for tracker in trackers:
            tracked_ids.update(self._track_ids(getattr(tracker, "tracked_stracks", None)))
            lost_ids.update(self._track_ids(getattr(tracker, "lost_stracks", None)))
            removed_ids.update(self._track_ids(
                getattr(tracker, "removed_stracks_frame", None)
            ))
        return TrackerLifecycle(
            frozenset(tracked_ids),
            frozenset(lost_ids),
            frozenset(removed_ids),
        )

    @staticmethod
    def _track_ids(tracks) -> set[int]:
        if tracks is None:
            return set()
        return {
            int(track.track_id)
            for track in tracks
            if getattr(track, "track_id", None) is not None
        }

    def reset(self):
        self._lifecycle = None
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
