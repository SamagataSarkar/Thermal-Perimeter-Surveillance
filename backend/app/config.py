import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = (
    PROJECT_ROOT
    / "runs"
    / "detect"
    / "models"
    / "thermal_perimeter_yolo11n-2"
    / "weights"
    / "best.pt"
)
DATABASE_URL = os.getenv("THERMAL_DATABASE_URL", "sqlite:///./backend-data/thermal.db")
SNAPSHOT_DIRECTORY = os.getenv(
    "THERMAL_SNAPSHOT_DIRECTORY", os.path.join("backend-data", "snapshots")
)


def resolve_model_path(model_path: str | os.PathLike[str] | None = None) -> str:
    configured_path = model_path if model_path is not None else os.getenv(
        "THERMAL_MODEL_PATH"
    )
    path = Path(configured_path) if configured_path else DEFAULT_MODEL_PATH
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path.resolve())


MODEL_PATH = resolve_model_path()
TRACKER_CONFIG = os.getenv("THERMAL_TRACKER_CONFIG", "custom_tracker.yaml")
ENTRY_DEBOUNCE_SECONDS = float(os.getenv("THERMAL_ENTRY_DEBOUNCE_SECONDS", "0.15"))
EXIT_DEBOUNCE_SECONDS = float(os.getenv("THERMAL_EXIT_DEBOUNCE_SECONDS", "0.25"))
TRANSITION_MIN_OBSERVATIONS = int(
    os.getenv("THERMAL_TRANSITION_MIN_OBSERVATIONS", "3")
)
GEOFENCE_HYSTERESIS_PIXELS = float(
    os.getenv("THERMAL_GEOFENCE_HYSTERESIS_PIXELS", "4.0")
)
DEFAULT_DWELL_THRESHOLD_SECONDS = float(
    os.getenv("THERMAL_DWELL_THRESHOLD_SECONDS", "3.0")
)
MIN_DWELL_THRESHOLD_SECONDS = 0.1
MAX_DWELL_THRESHOLD_SECONDS = 300.0


def resolve_inference_size(value: str | int | None = None) -> int:
    configured_value = value if value is not None else os.getenv(
        "THERMAL_INFERENCE_SIZE", "960"
    )
    try:
        inference_size = int(configured_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "THERMAL_INFERENCE_SIZE must be a positive integer"
        ) from exc
    if inference_size <= 0:
        raise ValueError("THERMAL_INFERENCE_SIZE must be a positive integer")
    return inference_size


INFERENCE_SIZE = resolve_inference_size()
APPLICATION_VERSION = os.getenv("THERMAL_APPLICATION_VERSION", "3.0.0")
