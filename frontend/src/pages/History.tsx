import { useEffect, useState } from 'react'
import { api } from '../api'
import type { EventRecord, Source, Zone } from '../types'
import { Card, Empty, ErrorState, Loading } from '../components/Ui'
import { EventTable } from '../components/EventTable'

export function History() {
  const [events,setEvents]=useState<EventRecord[]|null>(null);const [sources,setSources]=useState<Source[]>([]);const [zones,setZones]=useState<Zone[]>([]);const [type,setType]=useState('');const [status,setStatus]=useState('');const [source,setSource]=useState('');const [error,setError]=useState('')
  const load=()=>{const params=new URLSearchParams({limit:'100'});if(type)params.set('event_type',type);if(status)params.set('status',status);if(source)params.set('source_id',source);api.events(params.toString()).then(setEvents).catch(e=>setError(e.message))};useEffect(()=>{Promise.all([api.sources(),api.zones()]).then(([sourceItems,zoneItems])=>{setSources(sourceItems);setZones(zoneItems)}).catch(e=>setError(e.message))},[]);useEffect(()=>{load()},[type,status,source])
  if(error&&!events)return <ErrorState message={error} retry={()=>{setError('');load()}}/>;if(!events)return <Loading/>
  return <div className="page-stack"><Card><div className="filter-bar"><label>Source<select value={source} onChange={e=>setSource(e.target.value)}><option value="">All sources</option>{sources.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label>Event type<select value={type} onChange={e=>setType(e.target.value)}><option value="">All types</option>{['ENTRY','EXIT','DWELL','FIRST_OBSERVED_INSIDE'].map(v=><option key={v}>{v}</option>)}</select></label><label>Status<select value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>{['NEW','ACKNOWLEDGED','RESOLVED'].map(v=><option key={v}>{v}</option>)}</select></label></div></Card><Card><div className="card-heading"><div><p className="eyebrow">PERSISTED RECORDS</p><h2>Event history</h2></div><span className="subtext">{events.length} records</span></div>{events.length?<EventTable events={events} sources={sources} zones={zones}/>:<Empty label="No events match the current filters"/>}</Card></div>
}
