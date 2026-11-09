import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { Bell, Volume2, VolumeX } from 'lucide-react'
import { api } from '../api'
import type { MonitorMessage } from '../types'

type AlarmContextValue = {
  audioEnabled: boolean
  audioPreference: boolean
  muted: boolean
  activeCount: number
  enableAudio: () => Promise<void>
  setMuted: (muted: boolean) => void
  testAlarm: () => void
  refreshAlerts: () => Promise<void>
  applyAlertUpdate: (alertId: number, status: string) => void
  audioBlocked: boolean
}

const AlarmContext = createContext<AlarmContextValue | null>(null)

function playTone(context: AudioContext) {
  const now = context.currentTime
  const oscillator = context.createOscillator()
  const gain = context.createGain()
  oscillator.type = 'square'
  oscillator.frequency.setValueAtTime(740, now)
  oscillator.frequency.linearRampToValueAtTime(520, now + 0.35)
  gain.gain.setValueAtTime(0.0001, now)
  gain.gain.exponentialRampToValueAtTime(0.16, now + 0.02)
  gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.38)
  oscillator.connect(gain).connect(context.destination)
  oscillator.start(now)
  oscillator.stop(now + 0.4)
}

export function AlarmProvider({ children }: { children: ReactNode }) {
  const [sessionIds, setSessionIds] = useState<number[]>([])
  const [audioEnabled, setAudioEnabled] = useState(false)
  const [audioPreference, setAudioPreference] = useState(
    () => localStorage.getItem('thermal-audible-alarm-enabled') === 'true',
  )
  const [audioBlocked, setAudioBlocked] = useState(false)
  const [muted, setMuted] = useState(() => localStorage.getItem('thermal-alarm-muted') === 'true')
  const [active, setActive] = useState<Set<number>>(new Set())
  const audioRef = useRef<AudioContext | null>(null)
  const socketsRef = useRef<WebSocket[]>([])
  const notifiedRef = useRef<Set<number>>(new Set())

  const refreshAlerts = async () => {
    if (!api.alerts) return
    const alerts = await api.alerts('status=NEW&limit=200')
    setActive(new Set(alerts
      .filter((alert) => alert.alert_type === 'DWELL' && alert.severity === 'HIGH')
      .map((alert) => alert.id)))
  }

  const applyAlertUpdate = (alertId: number, status: string) => {
    if (status === 'NEW') return
    setActive((current) => {
      const next = new Set(current)
      next.delete(alertId)
      return next
    })
    void refreshAlerts().catch(() => undefined)
  }

  useEffect(() => {
    const load = () => api.activeSession().then((session) => {
      setSessionIds(session ? [session.id] : [])
    }).catch(() => setSessionIds([]))
    if (!api.activeSession) return
    void load()
    const timer = window.setInterval(load, 5000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    void refreshAlerts().catch(() => undefined)
    const timer = window.setInterval(() => { void refreshAlerts().catch(() => undefined) }, 5000)
    return () => window.clearInterval(timer)
  }, [])

  const handleMessage = (message: MonitorMessage) => {
    if (message.type === 'alert_created') {
      const id = Number(message.data.alert_id)
      void refreshAlerts().then(() => {
        if (id && message.data.alert_type === 'DWELL' && message.data.severity === 'HIGH'
            && !notifiedRef.current.has(id)
            && 'Notification' in window && Notification.permission === 'granted') {
          notifiedRef.current.add(id)
          const objectClass = message.data.object_class === 'vehicle' ? 'vehicle' : 'person'
          new Notification(`Possible ${objectClass} intrusion`, { body: `${objectClass} detection in restricted zone; operator verification required.` })
        }
      }).catch(() => setAudioBlocked(true))
    } else if (message.type === 'alert_updated') {
      const id = Number(message.data.alert_id)
      if (id) applyAlertUpdate(id, String(message.data.status ?? ''))
    }
  }

  useEffect(() => {
    socketsRef.current.forEach((socket) => socket.close())
    socketsRef.current = sessionIds.map((sessionId) => {
      const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? window.location.origin
      const url = new URL(`/ws/monitor/${sessionId}`, base)
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      const socket = new WebSocket(url)
      socket.onmessage = (event) => {
        try { handleMessage(JSON.parse(event.data) as MonitorMessage) } catch { /* ignore malformed messages */ }
      }
      return socket
    })
    return () => socketsRef.current.forEach((socket) => socket.close())
  }, [sessionIds])

  useEffect(() => {
    localStorage.setItem('thermal-alarm-muted', String(muted))
  }, [muted])

  useEffect(() => {
    localStorage.setItem('thermal-audible-alarm-enabled', String(audioPreference))
  }, [audioPreference])

  useEffect(() => {
    if (!audioPreference || audioRef.current) return
    const context = new AudioContext()
    audioRef.current = context
    context.resume().then(() => {
      if (context.state === 'running') {
        setAudioEnabled(true)
        setAudioBlocked(false)
      } else {
        setAudioBlocked(true)
      }
    }).catch(() => undefined)
  }, [audioPreference])

  useEffect(() => {
    if (!active.size || muted || !audioEnabled || !audioRef.current) return
    const timer = window.setInterval(() => {
      if (audioRef.current?.state === 'running') playTone(audioRef.current)
    }, 2500)
    playTone(audioRef.current)
    return () => window.clearInterval(timer)
  }, [active.size, muted, audioEnabled])

  const enableAudio = async () => {
    const context = audioRef.current ?? new AudioContext()
    audioRef.current = context
    await context.resume()
    if (context.state !== 'running') {
      setAudioBlocked(true)
      throw new Error('Browser audio permission was not granted')
    }
    setAudioBlocked(false)
    setAudioPreference(true)
    setAudioEnabled(true)
    if ('Notification' in window && Notification.permission === 'default') await Notification.requestPermission()
  }

  const testAlarm = () => {
    if (audioRef.current?.state === 'running') playTone(audioRef.current)
  }

  return <AlarmContext.Provider value={{ audioEnabled, audioPreference, muted, activeCount: active.size, enableAudio, setMuted, testAlarm, refreshAlerts, applyAlertUpdate, audioBlocked }}>
    {children}
    <div className={`alarm-banner ${active.size ? 'active' : ''}`}>
      <Bell size={18}/><strong>{active.size ? `${active.size} active high-priority alarm${active.size === 1 ? '' : 's'}` : 'No active alarms'}</strong>
      {!audioEnabled && <span>{audioBlocked ? 'Browser blocked playback; reactivate with a user interaction.' : 'Sound requires operator enablement.'}</span>}
      {audioEnabled && <span>{muted ? 'Muted' : 'Audible warning enabled'}</span>}
    </div>
  </AlarmContext.Provider>
}

export function useAlarm() {
  const value = useContext(AlarmContext)
  if (!value) throw new Error('useAlarm must be used inside AlarmProvider')
  return value
}

export function AlarmControls() {
  const { audioEnabled, muted, enableAudio, setMuted, testAlarm, audioBlocked } = useAlarm()
  const enable = () => { void enableAudio().catch(() => undefined) }
  return <div className="alarm-controls">
    {!audioEnabled && <button className="button primary" onClick={enable}><Volume2 size={15}/> {audioBlocked ? 'Reactivate audible alarm' : 'Enable audible alarm'}</button>}
    <button className="button ghost" onClick={() => setMuted(!muted)} disabled={!audioEnabled}>{muted ? <VolumeX size={15}/> : <Volume2 size={15}/>} {muted ? 'Unmute' : 'Mute'}</button>
    <button className="button ghost" onClick={testAlarm} disabled={!audioEnabled}>Test alarm</button>
  </div>
}
