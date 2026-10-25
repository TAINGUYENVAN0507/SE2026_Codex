import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'
import { MeetingListPage } from '../pages/MeetingListPage'
import { RemoteSummary } from '../features/meetings/RemoteSummary'
import { Transcript } from '../features/meetings/Transcript'
import { DemoStore } from '../features/meetings/DemoStore'
import { seedMeetings } from '../features/meetings/model'
import userMe from '../../../contracts/fixtures/api/user_me.json'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('FE-16 loading skeletons', () => {
  it('reserves list rows while the meeting API is loading', async () => {
    server.use(
      http.get('*/api/v1/meetings', () =>
        HttpResponse.json({ items: [], total: 0 }),
      ),
    )
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    client.setQueryData(['me'], userMe)
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <DemoStore>
            <MeetingListPage />
          </DemoStore>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(
      screen.getByRole('status', { name: 'Đang tải danh sách cuộc họp…' }),
    ).toHaveClass('loading-list')
    expect(await screen.findByText('Chưa có cuộc họp')).toBeInTheDocument()
  })
  it('renders a busy transcript skeleton until transcription completes', () => {
    render(
      <Transcript
        meeting={{ ...seedMeetings()[0], segments: [] }}
        pending
        position={0}
        onSeek={() => {}}
        onUpdate={() => {}}
      />,
    )
    expect(screen.getByRole('status')).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status')).toHaveClass('loading-transcript')
  })
  it('renders a summary skeleton while the API is loading', async () => {
    server.use(
      http.get('*/api/v1/meetings/:id/summary', () =>
        HttpResponse.json({ status: 'disabled', content: null }),
      ),
    )
    render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <RemoteSummary meeting={seedMeetings()[0]} onSeek={() => {}} />
      </QueryClientProvider>,
    )
    expect(screen.getByRole('status')).toHaveClass('loading-summary')
    expect(
      await screen.findByText('Tính năng tóm tắt hiện chưa được bật.'),
    ).toBeInTheDocument()
  })
})
