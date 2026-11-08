from ultralytics import YOLO
import torch

def start_training():
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"Active Device: {torch.cuda.get_device_name(0)}")

    # Load baseline pre-trained YOLO11 Nano model
    model = YOLO("yolo11n.pt")

    # Start fine-tuning
    model.train(
        data="datasets/unified/data.yaml",
        epochs=35,
        imgsz=640,
        batch=8,
        device=0,
        workers=2,
        amp=True,
        project="models",
        name="thermal_perimeter_yolo11n",
        save=True,
        save_period=5,
        patience=10
    )

if __name__ == "__main__":
    start_training()