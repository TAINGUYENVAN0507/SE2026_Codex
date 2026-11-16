import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest'
import meeting from '../../../../contracts/fixtures/api/meeting_processing.json'
import transcript from '../../../../contracts/fixtures/api/transcript_ready.json'
import summary from '../../../../contracts/fixtures/api/summary_disabled.json'
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
  vi.useRealTimers()
})
afterAll(() => server.close())
async function advance(ms: number) {
  await act(() => vi.advanceTimersByTimeAsync(ms))
}
async function setup(status: 'failed' | 'pending') {
  let requests = 0
  server.use(
    http.get('*/api/v1/meetings/:id/summary', () => {
      requests++
      return HttpResponse.json({ ...summary, status })
    }),
  )
  vi.useFakeTimers()
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
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
  await advance(100)
  expect(requests).toBe(1)
  expect(client.getQueryData(['summary', meeting.id])).toMatchObject({ status })
  return () => requests
}

it('FE-20: API failed dừng GET summary, sau 15 giây vẫn đúng một request', async () => {
  const count = await setup('failed')
  expect(screen.getByRole('button', { name: 'Tạo lại tóm tắt' })).toBeVisible()
  for (let second = 0; second < 15; second++) await advance(1000)
  expect(count()).toBe(1)
})

it('FE-20: API pending tiếp tục GET summary ở nhịp 5 giây', async () => {
  const count = await setup('pending')
  await advance(4800)
  expect(count()).toBe(1)
  await advance(200)
  expect(count()).toBe(2)
  expect(screen.getByText('Đang tạo tóm tắt…')).toBeVisible()
})
