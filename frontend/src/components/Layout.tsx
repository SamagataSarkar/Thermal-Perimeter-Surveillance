import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Activity, Bell, Camera, ChevronLeft, Gauge, LayoutDashboard, Menu, Settings, X } from 'lucide-react'

const links = [
  ['/','Overview',LayoutDashboard],
  ['/live','Live Monitoring',Camera],
  ['/alerts','Alerts & Events',Bell],
  ['/history','Event History',Activity],
  ['/configuration','Configuration',Settings],
  ['/performance','System Performance',Gauge],
] as const

export function Layout() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const title = links.find(([path]) => path === location.pathname)?.[1] ?? 'Overview'
  return <div className="app-shell">
    <button className="mobile-menu" aria-label="Open navigation" onClick={() => setOpen(true)}><Menu size={20} /></button>
    {open && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setOpen(false)} />}
    <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
      <div className="brand"><div className="brand-mark">TP</div><div><strong>THERMAL</strong><span>PERIMETER SURVEILLANCE</span></div>{open && <button className="icon-button mobile-close" aria-label="Close navigation" onClick={() => setOpen(false)}><X size={18}/></button>}</div>
      <nav aria-label="Primary navigation">{links.map(([path, label, Icon]) => <NavLink key={path} to={path} end={path === '/'} onClick={() => setOpen(false)} className={({isActive}) => isActive ? 'nav-item active' : 'nav-item'}><Icon size={18}/><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-footer"><span className="status-dot online" /> Backend-linked dashboard</div>
    </aside>
    <main className="main-content"><header className="page-header"><div><p className="eyebrow">OPERATIONS CONSOLE / 2026</p><h1>{title}</h1></div><div className="header-status"><span className="status-dot online" /> Live system</div></header><Outlet /></main>
  </div>
}
