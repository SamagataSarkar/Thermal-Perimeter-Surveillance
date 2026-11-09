import { describe, expect, it } from 'vitest'
import { eventClass, formatNumber } from '../utils'
import type { EventRecord } from '../types'

describe('frontend utilities', () => {
  it('preserves unavailable backend metrics', () => {
    expect(formatNumber(null)).toBe('Unavailable')
    expect(formatNumber(undefined)).toBe('Unavailable')
  })
  it('uses supplied object classes without inventing intent', () => {
    const event = { details: { object_class: 'person' } } as EventRecord
    expect(eventClass(event)).toBe('person')
  })
})
