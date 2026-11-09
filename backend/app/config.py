import os


DATABASE_URL = os.getenv("THERMAL_DATABASE_URL", "sqlite:///./backend-data/thermal.db")
SNAPSHOT_DIRECTORY = os.getenv(
    "THERMAL_SNAPSHOT_DIRECTORY", os.path.join("backend-data", "snapshots")
)
MODEL_PATH = os.getenv("THERMAL_MODEL_PATH", "yolo11n.pt")
TRACKER_CONFIG = os.getenv("THERMAL_TRACKER_CONFIG", "custom_tracker.yaml")
APPLICATION_VERSION = os.getenv("THERMAL_APPLICATION_VERSION", "3.0.0")
