import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  expect,
  it,
  vi,
} from 'vitest'
import { FetchXHR } from '../test/FetchXHR'
import { NewMeetingPage } from './NewMeetingPage'
import { DemoStore } from '../features/meetings/DemoStore'
import user from '../../../contracts/fixtures/api/user_me.json'
import config from '../../../contracts/fixtures/api/config.json'
import created from '../../../contracts/fixtures/api/meeting_created.json'

const server = setupServer()
const clients: QueryClient[] = []
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() => {
  vi.stubGlobal('XMLHttpRequest', FetchXHR)
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:date-test')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
})
afterEach(async () => {
  cleanup()
  for (const client of clients.splice(0)) {
    await client.cancelQueries()
    client.clear()
  }
  server.resetHandlers()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
afterAll(() => server.close())

it.each([true, false])(
  'FE-05: 422 ngày họp (chi tiết trường: %s) giữ file/tên và đổi key sau sửa ngày',
  async (fieldDetails) => {
    const sent = vi.spyOn(FetchXHR.prototype, 'send')
    const keys: (string | null)[] = []
    let meetings = 0
    server.use(
      http.post('*/api/v1/meetings', ({ request }) => {
        keys.push(request.headers.get('Idempotency-Key'))
        if (keys.length === 1)
          return HttpResponse.json(
            {
              error: {
                code: 'VALIDATION_ERROR',
                message: 'CANARY_RAW_DATE',
                request_id: null,
                details: fieldDetails
                  ? [
                      {
                        loc: ['body', 'meeting_date'],
                        type: 'string_pattern_mismatch',
                        msg: 'CANARY_RAW_DATE',
                      },
                    ]
                  : null,
              },
            },
            { status: 422 },
          )
        meetings++
        return HttpResponse.json(created, { status: 201 })
      }),
    )
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity } },
    })
    clients.push(client)
    client.setQueryData(['me'], user)
    client.setQueryData(['config'], config)
    render(
      <QueryClientProvider client={client}>
        <DemoStore>
          <MemoryRouter initialEntries={['/meetings/new']}>
            <Routes>
              <Route path="/meetings/new" element={<NewMeetingPage />} />
              <Route path="/meetings/:id" element={<h1>Chi tiết vừa tạo</h1>} />
            </Routes>
          </MemoryRouter>
        </DemoStore>
      </QueryClientProvider>,
    )
    fireEvent.change(screen.getByLabelText('Chọn file audio'), {
      target: {
        files: [new File(['synthetic'], 'date.wav', { type: 'audio/wav' })],
      },
    })
    fireEvent.change(screen.getByRole('textbox', { name: 'Tên cuộc họp' }), {
      target: { value: 'Tên đã nhập' },
    })
    fireEvent.change(screen.getByLabelText('Ngày họp'), {
      target: { value: '2026-11-24' },
    })
    fireEvent.click(
      screen.getByRole('checkbox', { name: /Tôi xác nhận đã có sự đồng ý/ }),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Tạo biên bản' }))
    const message = fieldDetails
      ? 'Ngày họp chưa hợp lệ. Hãy chọn lại ngày rồi thử lại.'
      : 'Thông tin chưa hợp lệ. Hãy kiểm tra ngày họp và tiêu đề rồi thử lại.'
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(message)
    const date = screen.getByLabelText('Ngày họp')
    expect(date).toHaveAccessibleDescription(message)
    expect(date.closest('details')).toHaveAttribute('open')
    expect(date.closest('.field')).toContainElement(alert)
    expect(date).toHaveAttribute('aria-invalid', String(fieldDetails))
    expect(alert).not.toHaveTextContent('CANARY_RAW_DATE')
    expect(screen.getByText('date.wav')).toBeVisible()
    expect(screen.getByRole('textbox', { name: 'Tên cuộc họp' })).toHaveValue(
      'Tên đã nhập',
    )
    expect(
      screen.queryByRole('heading', { name: 'Chi tiết vừa tạo' }),
    ).not.toBeInTheDocument()
    expect(keys).toHaveLength(1)
    expect(meetings).toBe(0)
    fireEvent.change(date, { target: { value: '2026-11-25' } })
    expect(date).not.toHaveAttribute('aria-describedby')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Tạo biên bản' }))
    await waitFor(() => expect(keys).toHaveLength(2))
    expect(keys[0]).toBeTruthy()
    expect(keys[1]).toBeTruthy()
    expect(keys[1]).not.toBe(keys[0])
    expect(
      await screen.findByRole('heading', { name: 'Chi tiết vừa tạo' }),
    ).toBeVisible()
    expect(meetings).toBe(1)
    const [firstBody, secondBody] = sent.mock.calls.map(([body]) => body)
    expect(firstBody.get('meeting_date')).toBe('2026-11-24')
    expect(secondBody.get('meeting_date')).toBe('2026-11-25')
    expect(secondBody.get('title')).toBe('Tên đã nhập')
    expect(secondBody.get('file')).toBe(firstBody.get('file'))
  },
)
