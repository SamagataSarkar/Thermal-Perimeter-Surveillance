import { useEffect, useState } from 'react'
import { Bell, Check, CheckCheck, X } from 'lucide-react'
import { api } from '../api'
import { apiUrl } from '../api/client'
import type { AlertRecord, Source, Zone } from '../types'
import { formatTime, sourceName } from '../utils'
import { AlarmControls, useAlarm } from '../components/AlarmProvider'
import { Badge, Card, Empty, ErrorState, Loading, Notice } from '../components/Ui'

export function Alerts() {
  const [alerts, setAlerts] = useState<AlertRecord[] | null>(null)
  const [sources, setSources] = useState<Source[]>([])
  const [zones, setZones] = useState<Zone[]>([])
  const [evidence, setEvidence] = useState<AlertRecord | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const { refreshAlerts, applyAlertUpdate, activeCount } = useAlarm()
  const load = () => Promise.all([api.alerts('limit=100'), api.sources(), api.zones()])
    .then(([items, sourceItems, zoneItems]) => { setAlerts(items); setSources(sourceItems); setZones(zoneItems) })
    .catch((e) => setError(e.message))
  useEffect(() => { void load() }, [])
  const action = (alert: AlertRecord, kind: 'acknowledgeAlert' | 'resolveAlert' | 'dismissAlert') =>
    api[kind](alert.id).then((updated) => {
      setAlerts((current) => current?.map((item) => item.id === updated.id ? updated : item) ?? current)
      applyAlertUpdate(updated.id, updated.status)
      setMessage(`Alert ${kind.replace('Alert', '')}d`)
      return refreshAlerts()
    })
      .catch((e) => setError(e.message))
  if (error && !alerts) return <ErrorState message={error} retry={() => { setError(''); void load() }} />
  if (!alerts) return <Loading label="Loading alerts" />
  const open = alerts.filter((alert) => alert.status === 'NEW' || alert.status === 'ACKNOWLEDGED')
  const activeDwell = alerts.filter((alert) => alert.alert_type === 'DWELL' && alert.status === 'NEW')
  return <div className="page-stack">
    {(activeDwell.length > 0 || activeCount > 0) && <div className="intrusion-banner"><Bell size={20}/><div><strong>Possible intrusion — person or vehicle detection in restricted zone</strong><span>Operator verification required. Thermal detections may include stationary vegetation or other false positives.</span></div></div>}
    <Card><div className="card-heading"><div><p className="eyebrow">AUDIBLE WARNING</p><h2>Alarm controls</h2></div><AlarmControls /></div><p className="subtext">Audio is only activated after explicit browser interaction. New high-priority DWELL alerts repeat at a controlled interval until acknowledged, resolved, or dismissed.</p></Card>
    <div className="summary-grid"><Card className="summary-card"><div className="summary-icon amber"><Bell size={19}/></div><div><span className="summary-label">Open alerts</span><strong>{open.length}</strong><small>Requires operator review</small></div></Card><Card className="summary-card"><div className="summary-icon red"><Bell size={19}/></div><div><span className="summary-label">New</span><strong>{alerts.filter((alert) => alert.status === 'NEW').length}</strong><small>Unacknowledged alerts</small></div></Card><Card className="summary-card"><div className="summary-icon green"><CheckCheck size={19}/></div><div><span className="summary-label">Resolved</span><strong>{alerts.filter((alert) => alert.status === 'RESOLVED').length}</strong><small>Historical resolution</small></div></Card></div>
    {message && <Notice>{message}</Notice>}{error && <Notice tone="error">{error}</Notice>}
    <Card><div className="card-heading"><div><p className="eyebrow">ACTIONABLE INCIDENTS</p><h2>Alerts</h2></div></div>
      {alerts.length ? <div className="live-events">{alerts.map((alert) => <article className={`live-event alert-row ${alert.status === 'NEW' && alert.alert_type === 'DWELL' ? 'high-priority' : ''}`} key={alert.id}>
        <Badge tone={alert.severity}>{alert.severity}</Badge>
        <div className="alert-content"><div className="alert-title"><strong>{alert.title}</strong><Badge tone={alert.status}>{alert.status}</Badge></div><small>{formatTime(alert.created_at)} · {sourceName(sources, alert.source_id)} · {alert.object_class ?? (alert.class_id === 0 ? 'person' : alert.class_id === 1 ? 'vehicle' : 'unknown object')} · Track #{alert.track_id ?? '—'} · Geofence {zones.find((zone) => zone.id === alert.geofence_id)?.name ?? alert.geofence_id ?? '—'}</small><p>{alert.description} {alert.alert_type === 'DWELL' && `Configured threshold: ${alert.dwell_threshold ?? '—'}s; observed dwell: ${alert.observed_dwell_seconds ?? '—'}s.`}</p>
          <div className="row-actions">{alert.evidence_snapshot_id ? <button className="button ghost" onClick={() => setEvidence(alert)}>View Evidence</button> : <span className="subtext">Evidence unavailable</span>}{alert.status === 'NEW' && <button className="button ghost" onClick={() => action(alert, 'acknowledgeAlert')}><Check size={15}/> Acknowledge</button>}{(alert.status === 'NEW' || alert.status === 'ACKNOWLEDGED') && <><button className="button ghost" onClick={() => action(alert, 'resolveAlert')}><CheckCheck size={15}/> Resolve</button><button className="button ghost" onClick={() => action(alert, 'dismissAlert')}><X size={15}/> Dismiss</button></>}</div>
        </div>
      </article>)}</div> : <Empty label="No actionable alerts have been generated" />}
    </Card>
    {evidence && <div className="modal-backdrop" role="presentation" onClick={() => setEvidence(null)}><section className="modal evidence-modal" role="dialog" aria-modal="true" aria-labelledby="evidence-title" onClick={(event) => event.stopPropagation()}><div className="card-heading"><div><p className="eyebrow">EVIDENCE SNAPSHOT</p><h2 id="evidence-title">Alert #{evidence.id}</h2></div><button className="icon-button" aria-label="Close evidence" onClick={() => setEvidence(null)}><X size={18}/></button></div>{evidence.evidence_snapshot_id ? <img className="evidence-image" src={apiUrl(`/api/snapshots/${evidence.evidence_snapshot_id}/image`)} alt={`Evidence for alert ${evidence.id}`} /> : <Empty label="Evidence is unavailable" />}</section></div>}
  </div>
}
