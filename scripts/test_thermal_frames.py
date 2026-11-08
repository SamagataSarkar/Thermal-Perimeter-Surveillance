import os
import cv2
import glob
from ultralytics import YOLO

model = YOLO("runs/detect/models/thermal_perimeter_yolo11n-2/weights/best.pt")
val_images = glob.glob("datasets/unified/images/valid/*.jpg")

print(f"Testing on {len(val_images)} thermal validation images...")
for img_path in val_images[:10]:
    results = model.predict(img_path, conf=0.35, show=False)
    annotated = results[0].plot()
    
    cv2.imshow("Thermal Validation Ground Truth", annotated)
    if cv2.waitKey(800) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()