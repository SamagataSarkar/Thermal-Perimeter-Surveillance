import type { EventRecord, Source } from './types'

export const formatTime = (value?: string) =>
  value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—'

export const formatNumber = (value: number | null | undefined, suffix = '') =>
  value === null || value === undefined ? 'Unavailable' : `${value.toFixed(1)}${suffix}`

export const sourceName = (sources: Source[], id: number) =>
  sources.find((source) => source.id === id)?.name ?? `Source #${id}`

export const eventClass = (event: EventRecord) => event.details.object_class ?? 'Object not supplied'
