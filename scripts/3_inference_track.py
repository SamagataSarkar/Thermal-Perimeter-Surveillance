import cv2
import numpy as np
import math
from ultralytics import YOLO
import time
from collections import defaultdict
import threading

# ---------------- CONFIGURATION ----------------
MODEL_PATH = "runs/detect/models/thermal_perimeter_yolo11n-2/weights/best.pt"

# To test live latency handling, replace this with an IP Camera stream
# e.g., VIDEO_SOURCE = "rtsp://admin:password@192.168.1.100:554/stream1"
VIDEO_SOURCE = "demo_thermal2.mp4" 
OUTPUT_PATH = "export.mp4"

LOITER_ALERT_SECONDS = 3.0
track_history = defaultdict(lambda: [])
first_seen_inside = {}
# -----------------------------------------------

class ThreadedCamera:
    """Asynchronous RTSP stream reader to eliminate buffer latency."""
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src)
        self.ret, self.frame = self.cap.read()
        self.stopped = False

    def start(self):
        # Daemon thread ensures it dies automatically when the main program stops
        threading.Thread(target=self.update, args=(), daemon=True).start()
        return self

    def update(self):
        while not self.stopped:
            if not self.cap.isOpened():
                self.stopped = True
            else:
                self.ret, self.frame = self.cap.read()
            # 10ms sleep prevents the thread from maxing out the CPU on local MP4 testing
            time.sleep(0.01) 

    def read(self):
        return self.ret, self.frame

    def stop(self):
        self.stopped = True
        self.cap.release()

def run_surveillance():
    print(f"Loading weights from: {MODEL_PATH}")
    model = YOLO(MODEL_PATH)
    
    print(f"Connecting to video stream: {VIDEO_SOURCE}")
    stream = ThreadedCamera(VIDEO_SOURCE).start()
    
    # Allow the camera thread a brief moment to buffer the first frame
    time.sleep(1) 

    # Extract dimensions from the first valid frame
    ret, sample_frame = stream.read()
    if not ret or sample_frame is None:
        print("Error: Cannot read from video source.")
        stream.stop()
        return
        
    h, w = sample_frame.shape[:2]
    fps = 30 # Standardize to 30 for RTSP exports
    
    PERIMETER_POLYGON = np.array([
        [int(w * 0.25), int(h * 0.50)],   
        [int(w * 0.75), int(h * 0.50)],   
        [w, h],                           
        [0, h]                            
    ], np.int32).reshape((-1, 1, 2))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, (w, h))

    while True:
        ret, original_frame = stream.read()
        if not ret or original_frame is None:
            break

        current_time = time.time()

        # ==========================================
        # 1. CLAHE THERMAL PREPROCESSING
        # ==========================================
        # Convert raw frame to grayscale
        gray_frame = cv2.cvtColor(original_frame, cv2.COLOR_BGR2GRAY)
        
        # Apply Contrast Limited Adaptive Histogram Equalization
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_gray = clahe.apply(gray_frame)
        
        # Convert back to 3-channel BGR for YOLO compatibility
        frame = cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2BGR)
        # ==========================================

        # Run YOLO strictly on the high-contrast CLAHE frame
        results = model.track(frame, persist=True, tracker="custom_tracker.yaml", conf=0.30, iou=0.5, verbose=False)

        # Draw Geofence Overlay
        overlay = frame.copy()
        cv2.polylines(frame, [PERIMETER_POLYGON], isClosed=True, color=(0, 255, 255), thickness=2)
        cv2.fillPoly(overlay, [PERIMETER_POLYGON], color=(0, 50, 120))
        cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)

        if results[0].boxes and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().tolist()
            class_ids = results[0].boxes.cls.int().cpu().tolist()
            confs = results[0].boxes.conf.cpu().numpy()
            class_names = model.names

            for box, track_id, cls_id, conf in zip(boxes, track_ids, class_ids, confs):
                x1, y1, x2, y2 = map(int, box)
                box_width, box_height = x2 - x1, y2 - y1
                tracking_point = (int((x1 + x2) / 2), y2)
                
                history = track_history[track_id]
                history.append(tracking_point)
                if len(history) > 25: 
                    history.pop(0)

                kinematic_tag = ""
                if cls_id == 3 and len(history) >= 20:
                    start_pt, curr_pt = history[0], history[-1]
                    disp = math.hypot(curr_pt[0] - start_pt[0], curr_pt[1] - start_pt[1])
                    kinematic_tag = "- [HOVERING]" if disp < 15.0 else "- [IN FLIGHT]"
                elif cls_id == 0 and box_height > 0:
                    if (box_width / box_height) > 1.2:
                        kinematic_tag = "- [CRAWLING]"

                is_inside = cv2.pointPolygonTest(PERIMETER_POLYGON, tracking_point, measureDist=False) >= 0
                threat_status = "CLEAR"
                color = (0, 255, 0)

                if is_inside:
                    if track_id not in first_seen_inside:
                        first_seen_inside[track_id] = current_time
                    dwell = current_time - first_seen_inside[track_id]
                    if dwell >= LOITER_ALERT_SECONDS:
                        threat_status = f"LOITERING ({dwell:.1f}s)"
                        color = (0, 0, 255)
                    else:
                        threat_status = "ZONE ENTRY"
                        color = (0, 165, 255)
                else:
                    first_seen_inside.pop(track_id, None)

                if len(history) > 1:
                    pts = np.array(history, np.int32).reshape((-1, 1, 2))
                    cv2.polylines(frame, [pts], isClosed=False, color=color, thickness=2)

                entity_name = class_names.get(cls_id, f"cls_{cls_id}")
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"ID {track_id} | {entity_name} {kinematic_tag} ({conf:.2f}) [{threat_status}]", (x1, max(25, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)

        out.write(frame)
        cv2.imshow("Thermal Perimeter Surveillance", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'): 
            break

    # Graceful exit for the daemon thread
    stream.stop()
    out.release()
    cv2.destroyAllWindows()
    print(f"\n[SUCCESS] Defense presentation video successfully exported to: {OUTPUT_PATH}")

if __name__ == "__main__":
    run_surveillance()