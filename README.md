# Thermal Perimeter Surveillance

**Official project title:** Development of a Video Surveillance System for Object Detection and Intrusion Monitoring.

This repository contains the Phase 1 stabilized inference engine for the Thermal Perimeter Surveillance application. It uses the existing YOLO11n checkpoint, OpenCV thermal preprocessing, and Ultralytics ByteTrack.

## Architecture

```text
VideoSource -> ThermalPreprocessor -> Detector/Ultralytics ByteTrack
            -> Geofence -> EventEngine -> FrameAnnotator
            -> MetricsCollector
```

The reusable runtime modules are in [`scripts/inference`](scripts/inference). Recorded videos are processed sequentially using source timestamps. Live sources use a bounded latest-frame queue and monotonic timestamps.

## Environment setup

Use the existing environment; no additional packages are required:

```powershell
.\thermal_env\Scripts\Activate.ps1
```

The model, videos, and datasets are local artifacts and may not be present in a fresh Git clone.

## Model and tracker configuration

The demonstration defaults are:

```text
Model:   runs/detect/models/thermal_perimeter_yolo11n-2/weights/best.pt
Source:  demo_thermal2.mp4
Output:  export.mp4
Tracker: custom_tracker.yaml
```

All paths can be overridden with command-line options.

## Running the demonstration

```powershell
.\thermal_env\Scripts\python.exe scripts\3_inference_track.py
```

For headless execution:

```powershell
.\thermal_env\Scripts\python.exe scripts\3_inference_track.py --no-display
```

Press `q` in the OpenCV window to stop early.

## Running tests

```powershell
.\thermal_env\Scripts\python.exe -m unittest discover -s tests -v
```

The geofence and event-engine tests use synthetic observations and do not load the YOLO model or require CUDA.
