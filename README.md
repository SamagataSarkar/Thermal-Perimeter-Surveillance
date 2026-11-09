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

## Phase 3 backend

The backend exposes a FastAPI application at `backend.app.main:app`. API routes
delegate source, zone, session, event, snapshot and metric work to SQLAlchemy
and a background runtime worker. The worker is the only integration point that
invokes the existing Phase 1 `InferenceService`; it does not duplicate YOLO,
ByteTrack, preprocessing or geofence logic.

Start it on Windows from the repository root:

```powershell
.\thermal_env\Scripts\Activate.ps1
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The main endpoints are:

```text
GET/POST       /api/sources
GET/PUT/DELETE /api/sources/{source_id}
GET/POST       /api/zones
GET/PUT/DELETE /api/zones/{zone_id}
POST           /api/sessions/start
POST           /api/sessions/{session_id}/stop
GET            /api/sessions
GET            /api/events
POST           /api/events/{event_id}/acknowledge
POST           /api/events/{event_id}/resolve
GET            /api/snapshots
POST           /api/snapshots/capture
GET            /api/snapshots/{snapshot_id}/image
GET            /api/sessions/{session_id}/metrics
GET            /api/stream/{session_id}
GET            /api/health
WS             /ws/monitor/{session_id}
```

Register a recorded video and zone, then start a session:

```powershell
$source = Invoke-RestMethod http://127.0.0.1:8000/api/sources -Method Post `
  -ContentType 'application/json' `
  -Body '{"name":"Demo","source_type":"FILE","source_uri":"demo_thermal.mp4"}'
Invoke-RestMethod "http://127.0.0.1:8000/api/zones?source_id=$($source.id)" -Method Post `
  -ContentType 'application/json' `
  -Body '{"name":"Perimeter","normalized_polygon":[[0.0,0.5],[1.0,0.5],[1.0,1.0],[0.0,1.0]]}'
Invoke-RestMethod http://127.0.0.1:8000/api/sessions/start -Method Post `
  -ContentType 'application/json' -Body "{`"source_id`":$($source.id)}"
```

Display an active annotated session with an HTML image element pointing to
`http://127.0.0.1:8000/api/stream/{session_id}`. WebSocket messages use the
shape `{type, session_id, timestamp, data}` and contain status, detection,
event, source-error and metric updates. Snapshots are stored under
`backend-data/snapshots/` by default; `THERMAL_SNAPSHOT_DIRECTORY` can change
that managed directory.

RTSP sources accept `rtsp://` URLs. Credentials are redacted from responses,
but are currently stored in the database as supplied; encryption at rest is
not implemented. RTSP hardware has not been tested in this repository. A
session supports one source at a time, while different sources can run
independently subject to available hardware. CPU/GPU metrics unavailable on a
host are reported as null.
