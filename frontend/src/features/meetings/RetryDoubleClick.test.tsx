import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest'
import meeting from '../../../../contracts/fixtures/api/meeting_processing.json'
import transcript from '../../../../contracts/fixtures/api/transcript_ready.json'
import summary from '../../../../contracts/fixtures/api/summary_ready.json'
import job from '../../../../contracts/fixtures/api/job_retry_scheduled.json'
import type { MeetingDetail, TranscriptData } from '../../api/client'
import { apiMeetingToView } from './apiModel'
import { RemoteSummary } from './RemoteSummary'

const server = setupServer()
let client: QueryClient
let release: (() => void) | undefined
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(async () => {
  release?.()
  cleanup()
  await client.cancelQueries()
  client.clear()
  server.resetHandlers()
})
afterAll(() => server.close())

it('VT-018: double-clicking retry on a failed summary sends one POST until it completes', async () => {
  const requests: { key: string | null; body: unknown }[] = []
  let completed = false
  const responseGate = new Promise<void>((resolve) => {
    release = resolve
  })
  server.use(
    http.get('*/api/v1/meetings/:id/summary', () =>
      HttpResponse.json(
        completed ? summary : { ...summary, status: 'failed', content: null },
      ),
    ),
    http.post('*/api/v1/meetings/:id/jobs', async ({ request }) => {
      requests.push({
        key: request.headers.get('Idempotency-Key'),
        body: await request.json(),
      })
      await responseGate
      completed = true
      return HttpResponse.json(
        { ...job, status: 'queued', progress: 5 / 6 },
        { status: 202 },
      )
    }),
  )
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  render(
    <QueryClientProvider client={client}>
      <RemoteSummary
        meeting={apiMeetingToView(
          meeting as MeetingDetail,
          transcript as TranscriptData,
        )}
        onSeek={() => {}}
      />
    </QueryClientProvider>,
  )
  const button = await screen.findByRole('button', {
    name: 'Tạo lại tóm tắt',
  })
  await userEvent.setup().dblClick(button)
  await waitFor(() => expect(requests).toHaveLength(1))
  expect(button).toBeDisabled()
  expect(requests[0].key).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
  )
  expect(requests[0].body).toEqual({ from_stage: 'summarize' })
  release?.()
  await screen.findByText(summary.content.overview)
  expect(requests).toHaveLength(1)
  expect(
    screen.queryByRole('button', { name: 'Tạo lại tóm tắt' }),
  ).not.toBeInTheDocument()
})
