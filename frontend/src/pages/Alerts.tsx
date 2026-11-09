import { useEffect, useState } from 'react'
import { Bell, Check, CheckCheck } from 'lucide-react'
import { api } from '../api'
import type { EventRecord, Snapshot, Source } from '../types'
import { EventTable } from '../components/EventTable'
import { EventDetails } from '../components/EventDetails'
import { Card, Empty, ErrorState, Loading, Notice } from '../components/Ui'

export function Alerts() {
  const [events, setEvents] = useState<EventRecord[] | null>(null)
  const [sources, setSources] = useState<Source[]>([])
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [selected, setSelected] = useState<EventRecord | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const load = () => Promise.all([api.events('limit=100'), api.sources(), api.snapshots()])
    .then(([eventItems, sourceItems, snapshotItems]) => {
      setEvents(eventItems); setSources(sourceItems); setSnapshots(snapshotItems)
    }).catch((e) => setError(e.message))
  useEffect(() => { void load() }, [])
  const action = (id: number, kind: 'acknowledge' | 'resolve') =>
    api[kind](id).then(() => { setMessage(`Event ${kind}d`); void load() }).catch((e) => setError(e.message))
  if (error && !events) return <ErrorState message={error} retry={() => { setError(''); void load() }} />
  if (!events) return <Loading />
  const open = events.filter((event) => event.status !== 'RESOLVED')
  return <div className="page-stack">
    <div className="summary-grid">
      <Card className="summary-card"><div className="summary-icon amber"><Bell size={19}/></div><div><span className="summary-label">Open alerts</span><strong>{open.length}</strong><small>Requires operator review</small></div></Card>
      <Card className="summary-card"><div className="summary-icon red"><Check size={19}/></div><div><span className="summary-label">New</span><strong>{events.filter((event) => event.status === 'NEW').length}</strong><small>Unacknowledged events</small></div></Card>
      <Card className="summary-card"><div className="summary-icon green"><CheckCheck size={19}/></div><div><span className="summary-label">Resolved</span><strong>{events.filter((event) => event.status === 'RESOLVED').length}</strong><small>Historical resolution</small></div></Card>
    </div>
    {message && <Notice>{message}</Notice>}{error && <Notice tone="error">{error}</Notice>}
    <Card><div className="card-heading"><div><p className="eyebrow">OPERATOR QUEUE</p><h2>Alerts & events</h2></div></div>{events.length ? <EventTable events={events} sources={sources} onAction={action} onSelect={setSelected}/> : <Empty label="No monitoring events have been generated"/>}</Card>
    {selected && <EventDetails event={selected} sources={sources} snapshots={snapshots} onClose={() => setSelected(null)} />}
  </div>
}
