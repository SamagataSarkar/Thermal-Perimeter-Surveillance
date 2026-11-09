import { useEffect, useRef, useState, type MouseEvent } from 'react'

export function PolygonEditor({ value, onChange }: { value: [number, number][]; onChange: (points: [number, number][]) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const [points, setPoints] = useState(value)
  useEffect(() => setPoints(value), [value])
  const update = (next: [number, number][]) => { setPoints(next); onChange(next) }
  const click = (event: MouseEvent) => {
    const box = ref.current?.getBoundingClientRect()
    if (!box) return
    update([...points, [Math.min(1, Math.max(0, (event.clientX - box.left) / box.width)), Math.min(1, Math.max(0, (event.clientY - box.top) / box.height))]])
  }
  return <div className="polygon-editor">
    <div className="editor-canvas" ref={ref} onClick={click} role="application" aria-label="Polygon drawing area">
      <span className="editor-hint">Click to add perimeter points</span>
      <svg viewBox="0 0 1 1" preserveAspectRatio="none"><polygon points={points.map(([x,y]) => `${x},${y}`).join(' ')} /></svg>
      {points.map(([x,y], index) => <button key={`${x}-${y}-${index}`} className="polygon-point" style={{left:`${x*100}%`,top:`${y*100}%`}} aria-label={`Polygon point ${index + 1}`} onClick={(event) => event.stopPropagation()} />)}
    </div>
    <div className="editor-actions"><span>{points.length} points</span><button className="button ghost" onClick={() => update(points.slice(0, -1))}>Remove last</button><button className="button ghost" onClick={() => update([])}>Clear</button></div>
  </div>
}
