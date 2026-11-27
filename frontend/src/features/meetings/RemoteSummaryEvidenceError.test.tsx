import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest'
import ready from '../../../../contracts/fixtures/api/summary_ready.json'
import meetingFixture from '../../../../contracts/fixtures/api/meeting_processing.json'
import transcriptFixture from '../../../../contracts/fixtures/api/transcript_ready.json'
import type { MeetingDetail, TranscriptData } from '../../api/client'
import { apiMeetingToView } from './apiModel'
import { RemoteSummary } from './RemoteSummary'

const server = setupServer()
const clients: QueryClient[] = []
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(async () => {
  cleanup()
  for (const client of clients.splice(0)) {
    await client.cancelQueries()
    client.clear()
  }
  server.resetHandlers()
})
afterAll(() => server.close())

it('FE-12/18: 422 dẫn chứng hiện gần Lưu, giữ toàn bộ nháp và cho gửi lại', async () => {
  const requests: { content: typeof ready.content; version: number }[] = []
  server.use(
    http.get('*/api/v1/meetings/:id/summary', () => HttpResponse.json(ready)),
    http.put('*/api/v1/meetings/:id/summary', async ({ request }) => {
      const body = (await request.json()) as (typeof requests)[number]
      requests.push(body)
      return requests.length === 1
        ? HttpResponse.json(
            {
              error: {
                code: 'EVIDENCE_SEGMENT_NOT_IN_MEETING',
                message: 'CANARY_PRIVATE_EVIDENCE',
                details: null,
                request_id: null,
              },
            },
            { status: 422 },
          )
        : HttpResponse.json({
            ...ready,
            content: body.content,
            is_edited: true,
            version: body.version + 1,
          })
    }),
  )
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  })
  clients.push(client)
  render(
    <QueryClientProvider client={client}>
      <RemoteSummary
        meeting={apiMeetingToView(
          meetingFixture as MeetingDetail,
          transcriptFixture as TranscriptData,
        )}
        onSeek={vi.fn()}
      />
    </QueryClientProvider>,
  )
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Chỉnh sửa' }))
  const overview = screen.getByRole('textbox', { name: 'Chỉnh sửa tổng quan' })
  await user.clear(overview)
  await user.type(overview, 'Tổng quan nháp được giữ')
  await user.click(screen.getByRole('button', { name: 'Thêm ý chính' }))
  const added = screen.getByRole('textbox', { name: 'Ý chính 2' })
  await user.type(added, 'Ý mới chưa được lưu')
  await user.click(screen.getByRole('button', { name: 'Xóa decisions 1' }))
  const save = screen.getByRole('button', { name: 'Lưu' })
  await user.click(save)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(
    'Đoạn thoại dẫn chứng không thuộc cuộc họp này. Hãy kiểm tra lại.',
  )
  expect(save.closest('.notes-status')?.nextElementSibling).toBe(alert)
  expect(alert).not.toHaveTextContent('CANARY_PRIVATE_EVIDENCE')
  expect(overview).toHaveValue('Tổng quan nháp được giữ')
  expect(added).toHaveValue('Ý mới chưa được lưu')
  expect(screen.getByRole('textbox', { name: 'Ý chính 1' })).toHaveValue(
    ready.content.key_points[0].text,
  )
  expect(
    screen.queryByRole('textbox', { name: 'Quyết định 1' }),
  ).not.toBeInTheDocument()
  await waitFor(() => expect(save).toBeEnabled())
  const expected = {
    content: {
      overview: 'Tổng quan nháp được giữ',
      key_points: [
        ...ready.content.key_points,
        { text: 'Ý mới chưa được lưu', evidence_segment_ids: [] },
      ],
      decisions: [],
    },
    version: ready.version,
  }
  expect(requests).toEqual([expected])
  await user.click(save)
  expect(await screen.findByRole('button', { name: 'Chỉnh sửa' })).toBeEnabled()
  expect(requests).toEqual([expected, expected])
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(screen.getByText('Tổng quan nháp được giữ')).toBeVisible()
  expect(screen.getByText('Ý mới chưa được lưu')).toBeVisible()
  expect(
    screen.queryByText(ready.content.decisions[0].text),
  ).not.toBeInTheDocument()
})
