import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest'
import { handlers } from '../mocks/handlers'
import meeting from '../../../contracts/fixtures/api/meeting_processing.json'
import { MeetingProcessingPage } from './MeetingProcessingPage'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  cleanup()
  server.resetHandlers()
})
afterAll(() => server.close())
function setup() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false, gcTime: 0 } },
        })
      }
    >
      <MemoryRouter initialEntries={[`/meetings/${meeting.id}/processing`]}>
        <Routes>
          <Route
            path="/meetings/:meetingId/processing"
            element={<MeetingProcessingPage />}
          />
          <Route
            path="/meetings/:meetingId"
            element={<h1>Nội dung cuộc họp</h1>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
it('opens six stages directly and returns to the meeting without audio or editor on the progress page', async () => {
  setup()
  expect(await screen.findAllByRole('listitem')).toHaveLength(6)
  expect(
    screen.queryByRole('region', { name: 'Player audio cuộc họp' }),
  ).not.toBeInTheDocument()
  await userEvent.click(
    screen.getByRole('link', { name: 'Về nội dung cuộc họp' }),
  )
  expect(
    screen.getByRole('heading', { name: 'Nội dung cuộc họp' }),
  ).toBeInTheDocument()
})
it('shows an error instead of a stale processing card when a meeting cannot be loaded', async () => {
  server.use(
    http.get(
      '*/api/v1/meetings/:meetingId',
      () => new HttpResponse(null, { status: 404 }),
    ),
  )
  setup()
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Không tải được cuộc họp',
  )
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
})
it('handles a meeting without a job', async () => {
  server.use(
    http.get('*/api/v1/meetings/:meetingId', () =>
      HttpResponse.json({ ...meeting, latest_job_id: null, latest_job: null }),
    ),
  )
  setup()
  expect(
    await screen.findByText('Cuộc họp chưa có yêu cầu xử lý.'),
  ).toHaveAttribute('role', 'status')
})
