import { useEffect, useState } from 'react'
import { Activity, Camera, Database, Radio, Server } from 'lucide-react'
import { api } from '../api'
import type { EventRecord, Health, Session, Source } from '../types'
import { eventClass, formatTime, sourceName } from '../utils'
import { Card, Empty, ErrorState, Loading, Badge } from '../components/Ui'
import { EventTable } from '../components/EventTable'

export function Overview() {
  const [data, setData] = useState<{health: Health; sources: Source[]; sessions: Session[]; events: EventRecord[]} | null>(null)
  const [error, setError] = useState('')
  const load = () => Promise.all([api.health(), api.sources(), api.sessions(), api.events('limit=8')]).then(([health,sources,sessions,events]) => setData({health,sources,sessions,events})).catch((e) => setError(e.message))
  useEffect(() => { void load() }, [])
  if (error) return <ErrorState message={error} retry={() => {setError(''); void load()}} />
  if (!data) return <Loading />
  const active = data.sessions.filter((session) => session.status === 'RUNNING')
  return <div className="page-stack">
    <div className="summary-grid"><Summary icon={Server} label="Backend status" value={data.health.status.toUpperCase()} detail={`v${data.health.version}`} tone="green" /><Summary icon={Database} label="Database" value={data.health.database.connected ? 'Connected' : 'Unavailable'} detail="SQLite connectivity" tone={data.health.database.connected ? 'green' : 'red'} /><Summary icon={Camera} label="Configured sources" value={String(data.sources.length)} detail={`${data.sources.filter(s=>s.enabled).length} enabled`} /><Summary icon={Radio} label="Active sessions" value={String(active.length)} detail="Live workers" tone={active.length ? 'amber' : ''} /></div>
    <div className="two-column"><Card><div className="card-heading"><div><p className="eyebrow">MONITORING FEED</p><h2>Recent events</h2></div><Activity size={18}/></div>{data.events.length ? <EventTable events={data.events} sources={data.sources}/> : <Empty label="No events have been persisted yet" />}</Card><Card><div className="card-heading"><div><p className="eyebrow">CURRENT STATE</p><h2>Active sessions</h2></div></div>{active.length ? <div className="session-list">{active.map(session => <div className="session-row" key={session.id}><span className="status-dot online"/><div><strong>Session #{session.id}</strong><small>{sourceName(data.sources, session.source_id)}</small></div><Badge tone="running">RUNNING</Badge></div>)}</div> : <Empty label="No active monitoring sessions" />}</Card></div>
    <Card><div className="card-heading"><div><p className="eyebrow">SOURCE STATUS</p><h2>Configured sources</h2></div></div><div className="source-grid">{data.sources.map(source => <div className="source-tile" key={source.id}><span className={`status-dot ${source.enabled ? 'online' : ''}`}/><div><strong>{source.name}</strong><small>{source.source_type} · {source.enabled ? 'Enabled' : 'Disabled'}</small></div></div>)}</div>{!data.sources.length && <Empty label="No sources configured" />}</Card>
    <Card><div className="card-heading"><div><p className="eyebrow">ACTIVITY</p><h2>Latest timeline</h2></div></div>{data.events.length ? <div className="timeline">{data.events.slice(0,5).map(event => <div className="timeline-item" key={event.id}><span className="timeline-marker"/><div><strong>{event.event_type} · {eventClass(event)}</strong><small>{formatTime(event.occurred_at)} · {sourceName(data.sources,event.source_id)}</small></div></div>)}</div> : <Empty label="Activity will appear when monitoring produces events" />}</Card>
  </div>
}
function Summary({icon: Icon,label,value,detail,tone=''}: {icon: typeof Server; label:string;value:string;detail:string;tone?:string}) { return <Card className="summary-card"><div className={`summary-icon ${tone}`}><Icon size={19}/></div><div><span className="summary-label">{label}</span><strong>{value}</strong><small>{detail}</small></div></Card> }
