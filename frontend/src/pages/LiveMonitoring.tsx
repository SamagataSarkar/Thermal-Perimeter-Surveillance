import { useEffect, useState } from 'react'
import { Camera, CircleStop, LoaderCircle, Radio, Save, Wifi, WifiOff } from 'lucide-react'
import { api } from '../api'
import { apiUrl } from '../api/client'
import { useMonitoring } from '../components/MonitoringProvider'
import type { EventRecord, Metric, Session, Source, Zone } from '../types'
import { eventClass, formatNumber, formatTime } from '../utils'
import { Badge, Card, Empty, ErrorState, Notice } from '../components/Ui'

export function LiveMonitoring() {
  const [sources, setSources] = useState<Source[]>([])
  const [selected, setSelected] = useState<number>()
  const [zones, setZones] = useState<Zone[]>([])
  const [selectedZoneIds, setSelectedZoneIds] = useState<number[]>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { api.sources().then((items) => {setSources(items); setSelected(items[0]?.id)}).catch(e => setError(e.message)) }, [])
  useEffect(() => {
    if (!selected) {
      setZones([])
      setSelectedZoneIds([])
      return
    }
    api.zones(selected).then((items) => {
      setZones(items)
      setSelectedZoneIds(items.filter((zone) => zone.enabled).map((zone) => zone.id))
    }).catch((e) => setError(e.message))
  }, [selected])
  const { session, socketStatus, events, metrics, refresh, stop: stopMonitoring } = useMonitoring()
  const start = () => { if (!selected) return; setError(''); api.startSession({source_id:selected, zone_ids:selectedZoneIds}).then(() => refresh()).catch(e => setError(e.message)) }
  const stop = () => { stopMonitoring().then(() => setMessage('Session stopped')).catch(e => setError(e.message)) }
  if (error && !sources.length) return <ErrorState message={error} />
  const enabledZones = zones.filter((zone) => zone.enabled)
  const selectionComplete = enabledZones.length === 0 || selectedZoneIds.length > 0
  const toggleZone = (zoneId: number) => setSelectedZoneIds((current) => current.includes(zoneId) ? current.filter((id) => id !== zoneId) : [...current, zoneId])
  const zoneLabel = (zoneId?: number | null) => zoneId == null ? '' : ` · ${zones.find((zone) => zone.id === zoneId)?.name ?? `Zone #${zoneId}`}`
  return <div className="page-stack"><div className="toolbar"><div><p className="eyebrow">LIVE CONTROL</p><h2>Source monitoring</h2></div><div className="control-group"><label htmlFor="source-select">Video source</label><select id="source-select" value={selected ?? ''} onChange={e => setSelected(Number(e.target.value))}><option value="">Select a source</option>{sources.map(s => <option value={s.id} key={s.id}>{s.name} · {s.source_type}</option>)}</select>{session ? <button className="button danger" onClick={stop}><CircleStop size={16}/> Stop session</button> : <button className="button primary" disabled={!selected || !selectionComplete} onClick={start}><Radio size={16}/> Start session</button>}</div></div><Card className="zone-selection"><div className="card-heading"><div><p className="eyebrow">SESSION CONFIGURATION</p><h2>Geofence selection</h2><span className="subtext">{selectedZoneIds.length} selected</span></div><div className="row-actions"><button className="button ghost" disabled={!enabledZones.length} onClick={() => setSelectedZoneIds(enabledZones.map((zone) => zone.id))}>Select all</button><button className="button ghost" disabled={!enabledZones.length} onClick={() => setSelectedZoneIds([])}>Clear selection</button></div></div>{zones.length ? <div className="zone-options">{zones.map(zone => <label className={`zone-option ${zone.enabled ? '' : 'disabled'}`} key={zone.id}><input type="checkbox" checked={zone.enabled && selectedZoneIds.includes(zone.id)} disabled={!zone.enabled || Boolean(session)} onChange={() => toggleZone(zone.id)}/><span><strong>{zone.name}</strong><small>{zone.enabled ? 'Enabled' : 'Disabled'} · Zone #{zone.id}</small></span></label>)}</div> : <Empty label={selected ? 'No geofences configured for this source' : 'Select a source to choose geofences'} />}</Card>{message && <Notice>{message}</Notice>}{error && <Notice tone="error">{error}</Notice>}<div className="monitor-grid"><Card className="video-card"><div className="card-heading"><div><p className="eyebrow">ANNOTATED FEED</p><h2>{session ? `Session #${session.id}` : 'No active feed'}</h2></div>{session && <Badge tone={socketStatus === 'connected' ? 'running' : 'new'}>{socketStatus === 'connected' ? 'WEBSOCKET CONNECTED' : socketStatus.toUpperCase()}</Badge>}</div>{session ? <img className="mjpeg" src={apiUrl(`/api/stream/${session.id}`)} alt="Annotated thermal monitoring stream" /> : <div className="video-placeholder"><Camera size={36}/><span>Start a session to view annotated video</span></div>}<div className="video-footer"><span>{socketStatus === 'connected' ? <Wifi size={15}/> : <WifiOff size={15}/>} {socketStatus}</span><button className="button ghost" disabled={!session} onClick={() => session && api.captureSnapshot(session.id).then(()=>setMessage('Manual snapshot captured')).catch(e=>setError(e.message))}><Save size={15}/> Capture snapshot</button></div></Card><div className="monitor-side"><Card><div className="card-heading"><h2>Current metrics</h2></div><div className="metric-list"><Metric label="FPS" value={formatNumber(metrics?.fps)} /><Metric label="Inference latency" value={formatNumber(metrics?.inference_latency_ms,' ms')} /><Metric label="Dropped frames" value={formatNumber(metrics?.dropped_frames)} /><Metric label="CPU / GPU" value={`${formatNumber(metrics?.cpu_percent)} / ${formatNumber(metrics?.gpu_percent)}`} /></div></Card><Card><div className="card-heading"><h2>Live activity</h2></div>{events.length ? <div className="live-events">{events.map(event => <div className="live-event" key={event.id}><Badge tone={event.event_type}>{event.event_type}</Badge><div><strong>{eventClass(event)}{zoneLabel(event.geofence_id)}</strong><small>{formatTime(event.occurred_at)}{event.track_id ? ` · Track #${event.track_id}` : ''}</small></div></div>)}</div> : <Empty label="No events for this session" />}</Card></div></div></div>
}
function Metric({label,value}:{label:string;value:string}) { return <div className="metric-row"><span>{label}</span><strong>{value}</strong></div> }
