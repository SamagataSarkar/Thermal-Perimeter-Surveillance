import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from '../App'

vi.mock('../api', () => ({
  api: {
    health: vi.fn().mockResolvedValue({ status: 'ok', database: { connected: true }, active_sessions: 0, inference_available: true, version: 'test' }),
    sources: vi.fn().mockResolvedValue([]),
    sessions: vi.fn().mockResolvedValue([]),
    events: vi.fn().mockResolvedValue([]),
  },
}))

describe('application navigation', () => {
  it('renders the overview navigation and empty dashboard', async () => {
    render(<App />)
    expect(screen.getByText('Live Monitoring')).toBeTruthy()
    expect(await screen.findByText('No events have been persisted yet')).toBeTruthy()
  })
})
