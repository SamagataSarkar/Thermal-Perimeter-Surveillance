import { useEffect, useState } from 'react'
import { Camera, CircleStop, LoaderCircle, Radio, Save, Wifi, WifiOff } from 'lucide-react'
import { api } from '../api'
import { apiUrl } from '../api/client'
import { useWebSocket } from '../hooks/useWebSocket'
import type { EventRecord, Metric, Session, Source } from '../types'
import { eventClass, formatNumber, formatTime } from '../utils'
import { Badge, Card, Empty, ErrorState, Notice } from '../components/Ui'

export function LiveMonitoring() {
  const [sources, setSources] = useState<Source[]>([])
  const [selected, setSelected] = useState<number>()
  const [session, setSession] = useState<Session | null>(null)
  const [events, setEvents] = useState<EventRecord[]>([])
  const [metrics, setMetrics] = useState<Metric | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { api.sources().then((items) => {setSources(items); setSelected(items[0]?.id)}).catch(e => setError(e.message)) }, [])
  const socketStatus = useWebSocket(session?.id ?? null, (incoming) => {
    if (incoming.type === 'event_created') api.events(`session_id=${incoming.session_id}&limit=10`).then(setEvents).catch(() => undefined)
    if (incoming.type === 'metrics_update') setMetrics(incoming.data as Metric)
    if (incoming.type === 'source_error') setError(String(incoming.data.message ?? 'Source error'))
  })
  const start = () => { if (!selected) return; setError(''); api.startSession({source_id:selected}).then(setSession).catch(e => setError(e.message)) }
  const stop = () => { if (!session) return; api.stopSession(session.id).then((value) => {setSession(value); setMessage('Session stopped')}).catch(e => setError(e.message)) }
  useEffect(() => { if (session) { api.events(`session_id=${session.id}&limit=10`).then(setEvents).catch(() => undefined); api.metrics(session.id).then(items => setMetrics(items[0] ?? null)).catch(() => undefined) } }, [session])
  if (error && !sources.length) return <ErrorState message={error} />
  return <div className="page-stack"><div className="toolbar"><div><p className="eyebrow">LIVE CONTROL</p><h2>Source monitoring</h2></div><div className="control-group"><label htmlFor="source-select">Video source</label><select id="source-select" value={selected ?? ''} onChange={e => setSelected(Number(e.target.value))}><option value="">Select a source</option>{sources.map(s => <option value={s.id} key={s.id}>{s.name} · {s.source_type}</option>)}</select>{session ? <button className="button danger" onClick={stop}><CircleStop size={16}/> Stop session</button> : <button className="button primary" disabled={!selected} onClick={start}><Radio size={16}/> Start session</button>}</div></div>{message && <Notice>{message}</Notice>}{error && <Notice tone="error">{error}</Notice>}<div className="monitor-grid"><Card className="video-card"><div className="card-heading"><div><p className="eyebrow">ANNOTATED FEED</p><h2>{session ? `Session #${session.id}` : 'No active feed'}</h2></div>{session && <Badge tone={socketStatus === 'connected' ? 'running' : 'new'}>{socketStatus === 'connected' ? 'WEBSOCKET CONNECTED' : socketStatus.toUpperCase()}</Badge>}</div>{session ? <img className="mjpeg" src={apiUrl(`/api/stream/${session.id}`)} alt="Annotated thermal monitoring stream" /> : <div className="video-placeholder"><Camera size={36}/><span>Start a session to view annotated video</span></div>}<div className="video-footer"><span>{socketStatus === 'connected' ? <Wifi size={15}/> : <WifiOff size={15}/>} {socketStatus}</span><button className="button ghost" disabled={!session} onClick={() => session && api.captureSnapshot(session.id).then(()=>setMessage('Manual snapshot captured')).catch(e=>setError(e.message))}><Save size={15}/> Capture snapshot</button></div></Card><div className="monitor-side"><Card><div className="card-heading"><h2>Current metrics</h2></div><div className="metric-list"><Metric label="FPS" value={formatNumber(metrics?.fps)} /><Metric label="Inference latency" value={formatNumber(metrics?.inference_latency_ms,' ms')} /><Metric label="Dropped frames" value={formatNumber(metrics?.dropped_frames)} /><Metric label="CPU / GPU" value={`${formatNumber(metrics?.cpu_percent)} / ${formatNumber(metrics?.gpu_percent)}`} /></div></Card><Card><div className="card-heading"><h2>Live activity</h2></div>{events.length ? <div className="live-events">{events.map(event => <div className="live-event" key={event.id}><Badge tone={event.event_type}>{event.event_type}</Badge><div><strong>{eventClass(event)}</strong><small>{formatTime(event.occurred_at)}{event.track_id ? ` · Track #${event.track_id}` : ''}</small></div></div>)}</div> : <Empty label="No events for this session" />}</Card></div></div></div>
}
function Metric({label,value}:{label:string;value:string}) { return <div className="metric-row"><span>{label}</span><strong>{value}</strong></div> }
