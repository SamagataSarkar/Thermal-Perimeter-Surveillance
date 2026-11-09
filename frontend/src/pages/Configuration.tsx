import { useEffect, useState } from 'react'
import { Plus, Save, Trash2 } from 'lucide-react'
import { api } from '../api'
import type { Source, Zone } from '../types'
import { Card, Empty, Notice } from '../components/Ui'
import { PolygonEditor } from '../components/PolygonEditor'

export function Configuration() {
  const [sources, setSources] = useState<Source[]>([])
  const [zones, setZones] = useState<Zone[]>([])
  const [selected, setSelected] = useState<number>()
  const [name, setName] = useState('')
  const [uri, setUri] = useState('')
  const [type, setType] = useState('FILE')
  const [zoneName, setZoneName] = useState('Perimeter')
  const [polygon, setPolygon] = useState<[number, number][]>([])
  const [dwellThreshold, setDwellThreshold] = useState('3')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const load = () => Promise.all([api.sources(), api.settings()])
    .then(([items, settings]) => {
      setSources(items)
      setDwellThreshold(String(settings.dwell_threshold))
      if (!selected) setSelected(items[0]?.id)
    })
    .catch((e) => setError(e.message))

  useEffect(() => { void load() }, [])
  useEffect(() => {
    if (selected) api.zones(selected).then(setZones).catch((e) => setError(e.message))
  }, [selected])

  const addSource = () => api.createSource({ name, source_type: type, source_uri: uri, enabled: true })
    .then((item) => { setSources([...sources, item]); setName(''); setUri(''); setMessage('Source registered') })
    .catch((e) => setError(e.message))
  const addZone = () => selected && api.createZone({ source_id: selected, name: zoneName, normalized_polygon: polygon, enabled: true })
    .then((item) => { setZones([...zones, item]); setPolygon([]); setMessage('Geofence saved') })
    .catch((e) => setError(e.message))
  const saveThreshold = () => {
    const value = Number(dwellThreshold)
    if (!Number.isFinite(value) || value <= 0 || value > 300) {
      setError('Dwell threshold must be greater than 0 and no more than 300 seconds')
      return
    }
    api.updateDwellThreshold(value).then(() => setMessage('Dwell alarm threshold saved')).catch((e) => setError(e.message))
  }

  return <div className="page-stack">
    {error && <Notice tone="error">{error}</Notice>}{message && <Notice>{message}</Notice>}
    <Card>
      <div className="card-heading"><div><p className="eyebrow">ALARM POLICY</p><h2>Restricted-zone dwell alarm</h2></div></div>
      <div className="form-grid">
        <label>Dwell threshold (seconds)
          <input type="number" min="0.1" max="300" step="0.1" value={dwellThreshold} onChange={(e) => setDwellThreshold(e.target.value)} />
          <small className="subtext">A person-class detection must remain continuously inside a zone for this duration. Range: 0.1–300 seconds.</small>
        </label>
      </div>
      <button className="button primary" onClick={saveThreshold}><Save size={16}/> Save alarm threshold</button>
    </Card>
    <div className="two-column config-grid">
      <Card>
        <div className="card-heading"><div><p className="eyebrow">INPUT SOURCES</p><h2>Video sources</h2></div></div>
        <div className="form-grid"><label>Name<input value={name} onChange={(e) => setName(e.target.value)} placeholder="North perimeter" /></label><label>Type<select value={type} onChange={(e) => setType(e.target.value)}><option value="FILE">Recorded file</option><option value="RTSP">RTSP camera</option></select></label><label className="full">Recorded path or RTSP URL<input type={type === 'RTSP' ? 'password' : 'text'} value={uri} onChange={(e) => setUri(e.target.value)} placeholder={type === 'RTSP' ? '******camera/...' : 'demo_thermal.mp4'} /><small className="subtext">RTSP passwords are never displayed after submission.</small></label></div>
        <button className="button primary" disabled={!name || !uri} onClick={addSource}><Plus size={16}/> Add source</button>
        <div className="config-list">{sources.map((source) => <div className="config-row" key={source.id}><div><strong>{source.name}</strong><small>{source.source_type} · {source.source_uri}</small></div><button className="icon-button" title="Toggle source" aria-label="Toggle source" onClick={() => api.updateSource(source.id, { enabled: !source.enabled }).then(load)}><Save size={16}/></button><button className="icon-button danger-icon" title="Delete source" aria-label="Delete source" onClick={() => window.confirm(`Delete ${source.name}?`) && api.deleteSource(source.id).then(load).catch((e) => setError(e.message))}><Trash2 size={16}/></button></div>)}</div>
      </Card>
      <Card>
        <div className="card-heading"><div><p className="eyebrow">PERIMETER ZONES</p><h2>Geofence editor</h2></div></div>
        <label>Source<select value={selected ?? ''} onChange={(e) => setSelected(Number(e.target.value))}><option value="">Select source</option>{sources.map((source) => <option value={source.id} key={source.id}>{source.name}</option>)}</select></label>
        <label>Zone name<input value={zoneName} onChange={(e) => setZoneName(e.target.value)} /></label>
        <PolygonEditor value={polygon} onChange={setPolygon} />
        <button className="button primary" disabled={!selected || polygon.length < 3} onClick={addZone}><Save size={16}/> Save geofence</button>
        <div className="config-list">{zones.map((zone) => <div className="config-row" key={zone.id}><div><strong>{zone.name}</strong><small>{zone.normalized_polygon.length} normalized points · {zone.enabled ? 'Enabled' : 'Disabled'}</small></div><button className="icon-button danger-icon" title="Delete geofence" aria-label="Delete geofence" onClick={() => window.confirm(`Delete ${zone.name}?`) && api.deleteZone(zone.id).then(() => setZones(zones.filter((item) => item.id !== zone.id))).catch((e) => setError(e.message))}><Trash2 size={16}/></button></div>)}{!zones.length && <Empty label="No zones for this source" />}</div>
      </Card>
    </div>
  </div>
}
