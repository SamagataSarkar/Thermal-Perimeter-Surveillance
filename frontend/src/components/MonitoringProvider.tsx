import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from '../api'
import { useWebSocket } from '../hooks/useWebSocket'
import type { EventRecord, Metric, MonitorMessage, Session } from '../types'

type MonitoringContextValue = {
  session: Session | null
  socketStatus: ReturnType<typeof useWebSocket>
  metrics: Metric | null
  events: EventRecord[]
  refresh: () => Promise<void>
  stop: () => Promise<void>
}

const MonitoringContext = createContext<MonitoringContextValue | null>(null)

export function MonitoringProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [metrics, setMetrics] = useState<Metric | null>(null)
  const [events, setEvents] = useState<EventRecord[]>([])

  const refresh = async () => {
    const active = await api.activeSession?.()
    setSession(active ?? null)
    if (active) {
      const [recentEvents, recentMetrics] = await Promise.all([
        api.events(`session_id=${active.id}&limit=10`),
        api.metrics(active.id),
      ])
      setEvents(recentEvents)
      setMetrics(recentMetrics[0] ?? null)
    } else {
      setEvents([])
      setMetrics(null)
    }
  }

  useEffect(() => {
    if (!api.activeSession) return
    void refresh().catch(() => setSession(null))
    const timer = window.setInterval(() => { void refresh().catch(() => setSession(null)) }, 3000)
    return () => window.clearInterval(timer)
  }, [])

  const onMessage = (incoming: MonitorMessage) => {
    if (incoming.type === 'session_stopped'
      || (incoming.type === 'session_status' && incoming.data.status !== 'RUNNING')) {
      if (session?.id === incoming.session_id) {
        setSession(null)
        setEvents([])
        setMetrics(null)
      }
      return
    }
    if (incoming.type === 'event_created' && session) {
      void api.events(`session_id=${session.id}&limit=10`).then(setEvents).catch(() => undefined)
    }
    if (incoming.type === 'metrics_update') setMetrics(incoming.data as Metric)
    if (incoming.type === 'source_error') setSession(null)
  }
  const socketStatus = useWebSocket(session?.id ?? null, onMessage)

  const stop = async () => {
    if (!session) return
    await api.stopSession(session.id)
    setSession(null)
    setEvents([])
    setMetrics(null)
  }

  return <MonitoringContext.Provider value={{ session, socketStatus, metrics, events, refresh, stop }}>
    {children}
  </MonitoringContext.Provider>
}

export function useMonitoring() {
  const value = useContext(MonitoringContext)
  if (!value) throw new Error('useMonitoring must be used inside MonitoringProvider')
  return value
}
