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
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(async () => {
  cleanup()
  await client.cancelQueries()
  client.clear()
  server.resetHandlers()
})
afterAll(() => server.close())

it('shows retry for a partial meeting whose summary still says pending, then refreshes meeting state', async () => {
  let requests = 0
  server.use(
    http.get('*/api/v1/meetings/:id/summary', () =>
      HttpResponse.json(
        requests ? summary : { ...summary, status: 'pending', content: null },
      ),
    ),
    http.post('*/api/v1/meetings/:id/jobs', async ({ request }) => {
      expect(await request.json()).toEqual({ from_stage: 'summarize' })
      requests++
      return HttpResponse.json(
        { ...job, status: 'queued', progress: 5 / 6 },
        { status: 202 },
      )
    }),
  )
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  })
  const partial = { ...meeting, status: 'partial' } as MeetingDetail
  client.setQueryData(['meeting', meeting.id], partial)
  client.setQueryData(['meetings'], [partial])
  render(
    <QueryClientProvider client={client}>
      <RemoteSummary
        meeting={apiMeetingToView(partial, transcript as TranscriptData)}
        onSeek={() => {}}
      />
    </QueryClientProvider>,
  )
  await userEvent
    .setup()
    .click(await screen.findByRole('button', { name: 'Tạo lại tóm tắt' }))
  await screen.findByText(summary.content.overview)
  expect(requests).toBe(1)
  await waitFor(() => {
    expect(client.getQueryState(['meeting', meeting.id])?.isInvalidated).toBe(
      true,
    )
    expect(client.getQueryState(['meetings'])?.isInvalidated).toBe(true)
  })
})
