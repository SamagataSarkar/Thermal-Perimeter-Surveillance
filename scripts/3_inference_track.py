import argparse
import os

import cv2

from inference.detector import Detector
from inference.geofence import default_perimeter_zone
from inference.service import InferenceService
from inference.video_source import RecordedVideoSource


DEFAULT_MODEL_PATH = "runs/detect/models/thermal_perimeter_yolo11n-2/weights/best.pt"
DEFAULT_VIDEO_SOURCE = "demo_thermal.mp4"
DEFAULT_OUTPUT_PATH = "export.mp4"
DEFAULT_TRACKER_CONFIG = "custom_tracker.yaml"


def run_surveillance(model_path=DEFAULT_MODEL_PATH, video_source=DEFAULT_VIDEO_SOURCE,
                     output_path=DEFAULT_OUTPUT_PATH, tracker_config=DEFAULT_TRACKER_CONFIG,
                     dwell_seconds=3.0, show=True):
    if not os.path.exists(model_path):
        raise FileNotFoundError("Model checkpoint not found: {}".format(model_path))
    detector = Detector(model_path, tracker_config)
    service = InferenceService(detector, [default_perimeter_zone()], dwell_seconds)
    with RecordedVideoSource(video_source) as source:
        first_packet = source.read()
        if first_packet is None:
            raise RuntimeError("No frames available from video source: {}".format(video_source))
        height, width = first_packet.frame.shape[:2]
        fps = source.fps if source.fps > 0 else 30.0
        writer = cv2.VideoWriter(
            output_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )
        if not writer.isOpened():
            raise RuntimeError("Unable to open output video: {}".format(output_path))
        try:
            packet = first_packet
            while packet is not None:
                annotated, events, _ = service.process_packet(packet)
                for event in events:
                    print("[EVENT] {} track={} zone={} t={:.2f}".format(
                        event.event_type, event.track_id, event.zone_id, event.timestamp
                    ))
                writer.write(annotated)
                if show:
                    cv2.imshow("Thermal Perimeter Surveillance", annotated)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                packet = source.read()
        finally:
            writer.release()
            if show:
                cv2.destroyAllWindows()
    print("\n[SUCCESS] Defense presentation video successfully exported to: {}".format(output_path))


def main():
    parser = argparse.ArgumentParser(description="Thermal Perimeter Surveillance demonstration")
    parser.add_argument("--model", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--source", default=DEFAULT_VIDEO_SOURCE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--tracker", default=DEFAULT_TRACKER_CONFIG)
    parser.add_argument("--dwell-seconds", type=float, default=3.0)
    parser.add_argument("--no-display", action="store_true")
    args = parser.parse_args()
    run_surveillance(args.model, args.source, args.output, args.tracker,
                     args.dwell_seconds, not args.no_display)


if __name__ == "__main__":
    main()
