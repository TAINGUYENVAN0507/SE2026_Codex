import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { beforeAll, afterAll, afterEach, expect, it } from 'vitest'
import { DeleteMeetingButton } from './DeleteMeetingButton'
import { DemoStore } from './DemoStore'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  for (const key of [
    ['meeting', 'test'],
    ['transcript', 'test'],
    ['summary', 'test'],
    ['action-items', 'test'],
    ['edits', 'test', '', 1],
    ['job', 'job-test'],
    ['meetings', 1],
  ])
    client.setQueryData(key, { personal: 'synthetic' })
  client.setQueryData(['meeting', 'other'], { keep: true })
  render(
    <QueryClientProvider client={client}>
      <DemoStore>
        <MemoryRouter initialEntries={['/meetings/test']}>
          <Routes>
            <Route
              path="/meetings/test"
              element={
                <>
                  <DeleteMeetingButton meetingId="test" jobId="job-test" />
                  <p>Transcript đang đọc</p>
                </>
              }
            />
            <Route path="/meetings" element={<h1>Danh sách cuộc họp</h1>} />
          </Routes>
        </MemoryRouter>
      </DemoStore>
    </QueryClientProvider>,
  )
  return client
}
it('requires confirmation, supports cancel, then deletes and purges only related caches', async () => {
  let calls = 0
  server.use(
    http.delete('*/api/v1/meetings/test', () => {
      calls++
      return new HttpResponse(null, { status: 204 })
    }),
  )
  const client = setup()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Xóa cuộc họp' }))
  expect(screen.getByRole('alertdialog')).toHaveTextContent(
    'audio, transcript, tóm tắt, công việc (action item) và lịch sử chỉnh sửa',
  )
  expect(screen.getByRole('button', { name: 'Giữ lại' })).toHaveFocus()
  await user.click(screen.getByRole('button', { name: 'Giữ lại' }))
  expect(calls).toBe(0)
  await user.click(screen.getByRole('button', { name: 'Xóa cuộc họp' }))
  await user.click(screen.getByRole('button', { name: 'Xóa vĩnh viễn' }))
  await screen.findByRole('heading', { name: 'Danh sách cuộc họp' })
  expect(calls).toBe(1)
  expect(
    client
      .getQueryCache()
      .getAll()
      .map((q) => q.queryKey),
  ).toEqual([['meeting', 'other']])
})
it.each([0, 500, 503])(
  'keeps the page and cache when deletion fails (%s)',
  async (status) => {
    server.use(
      http.delete('*/api/v1/meetings/test', () =>
        status
          ? HttpResponse.json(
              {
                error: { code: 'INTERNAL_SERVER_ERROR', message: 'technical' },
              },
              { status },
            )
          : HttpResponse.error(),
      ),
    )
    const client = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Xóa cuộc họp' }))
    await userEvent.click(screen.getByRole('button', { name: 'Xóa vĩnh viễn' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Không xóa được cuộc họp',
    )
    expect(screen.getByText('Transcript đang đọc')).toBeInTheDocument()
    expect(client.getQueryData(['transcript', 'test'])).toBeDefined()
    expect(
      screen.queryByRole('heading', { name: 'Danh sách cuộc họp' }),
    ).not.toBeInTheDocument()
  },
)
