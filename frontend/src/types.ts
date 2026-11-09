export type SourceType = 'FILE' | 'RTSP'
export type EventType = 'ENTRY' | 'EXIT' | 'DWELL' | 'FIRST_OBSERVED_INSIDE'
export type EventStatus = 'NEW' | 'ACKNOWLEDGED' | 'RESOLVED'
export type AlertStatus = 'NEW' | 'ACKNOWLEDGED' | 'RESOLVED' | 'DISMISSED'
export type AlertSeverity = 'WARNING' | 'HIGH'
export type AlertType = 'ENTRY_WARNING' | 'DWELL'

export interface Health {
  status: string
  database: { connected: boolean }
  active_sessions: number
  inference_available: boolean
  version: string
}

export interface Source {
  id: number
  name: string
  source_type: SourceType
  source_uri: string
  enabled: boolean
  created_at?: string
  updated_at?: string
}

export interface Zone {
  id: number
  source_id: number
  name: string
  normalized_polygon: [number, number][]
  enabled: boolean
  created_at?: string
  updated_at?: string
}

export interface Session {
  id: number
  source_id: number
  status: string
  configuration_snapshot: Record<string, unknown>
  started_at: string
  ended_at?: string | null
}

export interface EventRecord {
  id: number
  source_id: number
  session_id: number
  geofence_id?: number | null
  track_id?: number | null
  event_type: EventType
  status: EventStatus
  occurred_at: string
  details: {
    object_class?: string | null
    confidence?: number | null
    [key: string]: unknown
  }
}

export interface AlertRecord {
    id: number
    event_id: number
    source_id: number
    session_id: number
    track_id?: number | null
    geofence_id?: number | null
    alert_type: AlertType
    severity: AlertSeverity
    title: string
    description: string
    evidence_snapshot_id?: number | null
    created_at: string
    acknowledged_at?: string | null
    resolved_at?: string | null
    status: AlertStatus
    dwell_threshold?: number | null
    observed_dwell_seconds?: number | null
    object_class?: string | null
    class_id?: number | null
}

export interface ApplicationSettings {
    dwell_threshold: number
}

export interface Snapshot {
  id: number
  source_id: number
  session_id: number
  event_id?: number | null
  file_path: string
  captured_at: string
  is_manual: boolean
  width?: number | null
  height?: number | null
  mime_type: string
}

export interface Metric {
  id?: number
  recorded_at?: string
  fps?: number | null
  inference_latency_ms?: number | null
  cpu_percent?: number | null
  gpu_percent?: number | null
  dropped_frames?: number | null
  live?: boolean
}

export interface MonitorMessage {
  type: 'session_status' | 'session_stopped' | 'detection_update' | 'event_created' | 'event_acknowledged' | 'event_resolved' | 'alert_created' | 'alert_updated' | 'metrics_update' | 'source_error'
  session_id: number
  timestamp: string
  data: Record<string, unknown>
}
