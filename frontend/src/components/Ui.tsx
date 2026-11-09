import type { ReactNode } from 'react'
import { AlertCircle, CheckCircle2, LoaderCircle, RefreshCw } from 'lucide-react'

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) { return <section className={`card ${className}`}>{children}</section> }
export function Loading({ label = 'Loading live data' }: { label?: string }) { return <div className="state"><LoaderCircle className="spin" size={22}/><span>{label}</span></div> }
export function Empty({ label = 'No records available' }: { label?: string }) { return <div className="state muted"><span>{label}</span></div> }
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) { return <div className="state error-state"><AlertCircle size={20}/><span>{message}</span>{retry && <button className="button ghost" onClick={retry}><RefreshCw size={15}/> Retry</button>}</div> }
export function Notice({ children, tone = 'success' }: { children: ReactNode; tone?: 'success' | 'error' }) { return <div className={`notice ${tone}`}><CheckCircle2 size={16}/>{children}</div> }
export function Badge({ children, tone = '' }: { children: ReactNode; tone?: string }) { return <span className={`badge ${tone.toLowerCase()}`}>{children}</span> }
