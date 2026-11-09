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

New person tracks require confidence `0.50`; other classes retain the
configured ByteTrack `new_track_thresh` of `0.40`. This applies only to
unmatched-track activation. Existing tracks still use the normal ByteTrack
association and recovery path.

Backend monitoring sessions use the custom-trained checkpoint at
`runs/detect/models/thermal_perimeter_yolo11n-2/weights/best.pt` by default.
The backend resolves this path from the project root rather than the current
terminal directory. Set `THERMAL_MODEL_PATH` to an absolute path or a path
relative to the project root to select another checkpoint. A session will not
start if the configured weight file is missing. The training script's
`yolo11n.pt` reference is only the base model used to start training and does
not affect backend monitoring sessions.

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
  -ContentType 'application/json' -Body "{`"source_id`":$($source.id),`"zone_ids`":[]}"
```

`zone_ids` is optional. When omitted, all enabled zones for the source are
selected for backward compatibility. When supplied, every ID must belong to
that source and be enabled; the selected IDs are fixed in the session
configuration for its lifetime. The dashboard's Live Monitoring page defaults
to all enabled zones and allows an operator to select any subset for the next
session without changing saved zones.

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

## Phase 4 frontend

The React/Vite dashboard is under [`frontend/`](frontend/). It uses the
backend as the source of truth for sources, zones, sessions, events, snapshots
and metrics. The live page consumes the existing MJPEG endpoint and monitoring
WebSocket; it does not run inference in the browser.

Install and start it on Windows:

```powershell
cd frontend
npm install
npm run dev
```

The Vite development server proxies `/api` and `/ws` to
`http://127.0.0.1:8000`. Set `VITE_API_BASE_URL` when the backend is hosted at
another origin. The dashboard routes are:

```text
/                    Overview
/live                Live Monitoring
/alerts              Alerts & Events
/history             Event History
/configuration       Sources and geofences
/performance         System Performance
```

Frontend checks:

```powershell
npm run typecheck
npm test
npm run build
```

The configuration page accepts recorded-file paths and RTSP URLs. RTSP
credentials are entered through a password field, are not persisted in browser
storage, and are not shown after submission. The backend currently stores
credentials without encryption at rest. The polygon editor emits normalized
coordinates in the same `[0, 1]` convention used by the backend.

The current backend event API supports offset/limit pagination and source,
session, event-type and status filters; it does not expose date-range filters.
The current geofence API also does not persist a per-zone dwell threshold, so
the dashboard uses the session-level dwell configuration supported by the
backend.

Geofence ENTRY and EXIT transitions use the following backend defaults:

```text
Entry debounce:              0.15 seconds
Exit debounce:               0.25 seconds
Minimum observations:        3
Hysteresis margin:            4.0 pixels
Tracking-loss grace period:   1.0 second
```

The hysteresis margin is measured in pixels in the processed video frame
coordinate system. It preserves the previous membership state inside the
neutral band between the enter and exit boundaries. Override these values with
`THERMAL_ENTRY_DEBOUNCE_SECONDS`, `THERMAL_EXIT_DEBOUNCE_SECONDS`,
`THERMAL_TRANSITION_MIN_OBSERVATIONS`, and
`THERMAL_GEOFENCE_HYSTERESIS_PIXELS`. Effective values are stored in each
session configuration snapshot.

Monitoring inference uses a default Ultralytics image size of `960`. Set
`THERMAL_INFERENCE_SIZE=832` or `THERMAL_INFERENCE_SIZE=640` (or another
positive integer) to select a different size without changing source code.
Invalid values are rejected during backend configuration loading, and the
effective size is stored in each session configuration snapshot. Confidence,
IoU/NMS, ByteTrack, model weights, and tracker settings are unchanged.
