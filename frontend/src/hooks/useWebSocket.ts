import { useEffect, useRef, useState } from 'react'
import type { MonitorMessage } from '../types'

export function useWebSocket(sessionId: number | null, onMessage: (message: MonitorMessage) => void) {
  const [status, setStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected')
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  useEffect(() => {
    if (!sessionId) {
      setStatus('disconnected')
      return
    }
    const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? window.location.origin
    const url = new URL(`/ws/monitor/${sessionId}`, base)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    setStatus('connecting')
    const socket = new WebSocket(url)
    socket.onopen = () => setStatus('connected')
    socket.onmessage = (event) => {
      try { onMessageRef.current(JSON.parse(event.data) as MonitorMessage) } catch { /* ignore malformed server messages */ }
    }
    socket.onclose = () => setStatus('disconnected')
    socket.onerror = () => setStatus('disconnected')
    return () => socket.close()
  }, [sessionId])

  return status
}
