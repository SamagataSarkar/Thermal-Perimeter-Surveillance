import { X } from 'lucide-react'
import { apiUrl } from '../api/client'
import type { EventRecord, Snapshot, Source } from '../types'
import { eventClass, formatNumber, formatTime, sourceName } from '../utils'
import { Badge } from './Ui'

export function EventDetails({ event, sources, snapshots, onClose }: {
  event: EventRecord
  sources: Source[]
  snapshots: Snapshot[]
  onClose: () => void
}) {
  const eventSnapshots = snapshots.filter((snapshot) => snapshot.event_id === event.id)
  return <div className="modal-backdrop" role="presentation" onClick={onClose}>
    <section className="modal" role="dialog" aria-modal="true" aria-labelledby="event-details-title" onClick={(click) => click.stopPropagation()}>
      <div className="card-heading"><div><p className="eyebrow">EVENT RECORD #{event.id}</p><h2 id="event-details-title">{event.event_type}</h2></div><button className="icon-button" aria-label="Close event details" onClick={onClose}><X size={18}/></button></div>
      <div className="detail-grid"><div><span>Timestamp</span><strong>{formatTime(event.occurred_at)}</strong></div><div><span>Status</span><strong><Badge tone={event.status}>{event.status}</Badge></strong></div><div><span>Object class</span><strong>{eventClass(event)}</strong></div><div><span>Confidence</span><strong>{formatNumber(event.details.confidence as number | null)}</strong></div><div><span>Source</span><strong>{sourceName(sources, event.source_id)}</strong></div><div><span>Tracking ID</span><strong>{event.track_id ?? 'Not supplied'}</strong></div><div><span>Geofence</span><strong>{event.geofence_id ?? 'Not supplied'}</strong></div></div>
      <h3 className="section-title">Associated snapshots</h3>
      {eventSnapshots.length ? <div className="snapshot-grid">{eventSnapshots.map(snapshot => <a href={apiUrl(`/api/snapshots/${snapshot.id}/image`)} target="_blank" rel="noreferrer" key={snapshot.id}><img src={apiUrl(`/api/snapshots/${snapshot.id}/image`)} alt={`Snapshot for event ${event.id}`} /></a>)}</div> : <p className="subtext">No snapshot is associated with this event.</p>}
    </section>
  </div>
}
