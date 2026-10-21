import { StrictMode } from 'react'
import { render, screen } from '@testing-library/react'
import { useQueryClient } from '@tanstack/react-query'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { DEMO_AUTH_KEY } from './RequireAuth'
import { AppProviders } from './AppProviders'

function LocationProbe() {
  return (
    <output aria-label="Đường dẫn hiện tại">{useLocation().pathname}</output>
  )
}

beforeEach(() => {
  // jsdom does not implement media playback; route unmount still calls cleanup.
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
  sessionStorage.setItem(DEMO_AUTH_KEY, 'true')
})

describe('FE-01 route scaffold', () => {
  it.each([
    ['/login', 'Chào mừng trở lại'],
    ['/meetings', 'Cuộc họp'],
    ['/meetings/new', 'Tạo cuộc họp mới'],
    ['/meetings/sprint-42', 'Họp kế hoạch sprint 42'],
    ['/meetings/unknown', 'Không tìm thấy cuộc họp'],
    ['/unknown', 'Không tìm thấy trang'],
  ])('renders %s in StrictMode', (path, heading) => {
    render(
      <StrictMode>
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      </StrictMode>,
    )
    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()
    expect(screen.getByText('Bản xem thử')).toBeInTheDocument()
  })

  it('redirects the root to the meeting list', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
        <LocationProbe />
      </MemoryRouter>,
    )
    expect(screen.getByLabelText('Đường dẫn hiện tại')).toHaveTextContent(
      '/meetings',
    )
    expect(
      screen.getByRole('heading', { name: 'Cuộc họp' }),
    ).toBeInTheDocument()
  })
})

describe('FE-01 providers', () => {
  it('provides the router and a stable QueryClient across rerenders', () => {
    const clients: ReturnType<typeof useQueryClient>[] = []
    function Probe() {
      const client = useQueryClient()
      clients.push(client)
      return <LocationProbe />
    }
    window.history.replaceState({}, '', '/meetings')
    try {
      const view = render(
        <AppProviders>
          <Probe />
        </AppProviders>,
      )
      expect(screen.getByLabelText('Đường dẫn hiện tại')).toHaveTextContent(
        '/meetings',
      )
      view.rerender(
        <AppProviders>
          <Probe />
        </AppProviders>,
      )
      expect(clients.length).toBeGreaterThan(1)
      expect(clients.every((client) => client === clients[0])).toBe(true)
      expect(clients[0].getDefaultOptions().mutations?.retry).toBe(false)
    } finally {
      window.history.replaceState({}, '', '/')
    }
  })
})
