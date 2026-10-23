import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DemoStore } from '../features/meetings/DemoStore'
import { NewMeetingPage } from './NewMeetingPage'

class FakeXHR {
  static instances: FakeXHR[] = []
  upload = { onprogress: null as ((event: ProgressEvent) => void) | null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null
  status = 0
  responseText = ''
  headers: Record<string, string> = {}
  aborted = false

  constructor() {
    FakeXHR.instances.push(this)
  }

  open() {}
  setRequestHeader(name: string, value: string) {
    this.headers[name] = value
  }
  send() {}
  abort() {
    this.aborted = true
    this.onabort?.()
  }
  finish(status: number, code: string) {
    this.status = status
    this.responseText = JSON.stringify({
      error: {
        code,
        message: 'Backend message',
        details: null,
        request_id: null,
      },
    })
    this.onload?.()
  }
}

function Location() {
  const location = useLocation()
  return <output aria-label="Đường dẫn hiện tại">{location.pathname}</output>
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <DemoStore>
        <MemoryRouter initialEntries={['/meetings/new']}>
          <Location />
          <Routes>
            <Route path="/meetings/new" element={<NewMeetingPage />} />
            <Route
              path="/meetings/:meetingId"
              element={<p>Trang chi tiết</p>}
            />
          </Routes>
        </MemoryRouter>
      </DemoStore>
    </QueryClientProvider>,
  )
}

async function submitFile() {
  const user = userEvent.setup()
  fireEvent.change(screen.getByLabelText('Chọn file audio'), {
    target: {
      files: [new File(['audio'], 'meeting.wav', { type: 'audio/wav' })],
    },
  })
  await user.click(
    screen.getByRole('checkbox', { name: /Tôi xác nhận đã có sự đồng ý/ }),
  )
  await user.click(screen.getByRole('button', { name: 'Tạo biên bản' }))
  expect(FakeXHR.instances).toHaveLength(1)
}

beforeEach(() => {
  vi.stubGlobal('XMLHttpRequest', FakeXHR)
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
})

afterEach(() => {
  FakeXHR.instances = []
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('FE-05 upload page', () => {
  it('stays on the upload page after cancellation and reuses the key on retry', async () => {
    const user = userEvent.setup()
    renderPage()
    await submitFile()
    const firstKey = FakeXHR.instances[0].headers['Idempotency-Key']
    expect(firstKey).toBeTruthy()

    await user.click(screen.getByRole('button', { name: 'Hủy tải lên' }))
    expect(FakeXHR.instances[0].aborted).toBe(true)
    expect(screen.getByRole('button', { name: 'Tạo biên bản' })).toBeEnabled()
    expect(screen.getByLabelText('Đường dẫn hiện tại')).toHaveTextContent(
      '/meetings/new',
    )
    expect(screen.queryByText('Trang chi tiết')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Tạo biên bản' }))
    expect(FakeXHR.instances[1].headers['Idempotency-Key']).toBe(firstKey)
  })

  it.each([
    [
      400,
      'BAD_REQUEST',
      'Yêu cầu không hợp lệ. Hãy kiểm tra thông tin rồi thử lại.',
    ],
    [409, 'CONFLICT', 'Yêu cầu xung đột với dữ liệu hiện tại. Hãy thử lại.'],
    [413, 'FILE_TOO_LARGE', 'File audio vượt quá dung lượng cho phép.'],
    [415, 'UNSUPPORTED_MEDIA_TYPE', 'Định dạng file audio chưa được hỗ trợ.'],
    [422, 'CONSENT_REQUIRED', 'Cần xác nhận sự đồng ý trước khi tiếp tục.'],
  ])(
    'shows the Vietnamese message for HTTP %i',
    async (status, code, message) => {
      renderPage()
      await submitFile()
      await act(async () => FakeXHR.instances[0].finish(status, code))
      expect(await screen.findByRole('alert')).toHaveTextContent(message)
      expect(screen.getByLabelText('Đường dẫn hiện tại')).toHaveTextContent(
        '/meetings/new',
      )
    },
  )
})
