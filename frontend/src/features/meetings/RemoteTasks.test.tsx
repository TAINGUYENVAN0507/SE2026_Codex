import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from 'vitest'
import meetingFixture from '../../../../contracts/fixtures/api/meeting_processing.json'
import transcriptFixture from '../../../../contracts/fixtures/api/transcript_ready.json'
import itemFixture from '../../../../contracts/fixtures/api/action_items.json'
import {
  listActionItems,
  type MeetingDetail,
  type TranscriptData,
} from '../../api/client'
import { handlers, resetMockMeetings } from '../../mocks/handlers'
import { apiMeetingToView } from './apiModel'
import { RemoteTasks } from './RemoteTasks'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  resetMockMeetings()
  vi.restoreAllMocks()
})
afterAll(() => server.close())

function renderTasks(onSeek = vi.fn()) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const meeting = apiMeetingToView(
    meetingFixture as MeetingDetail,
    transcriptFixture as TranscriptData,
  )
  render(
    <QueryClientProvider client={client}>
      <RemoteTasks meeting={meeting} onSeek={onSeek} />
    </QueryClientProvider>,
  )
  return onSeek
}

describe('FE-13 action item CRUD', () => {
  it('links action evidence to the matching transcript time', async () => {
    const user = userEvent.setup()
    const onSeek = renderTasks()
    const buttons = await screen.findAllByRole('button', {
      name: /Nghe bằng chứng từ/,
    })
    await user.click(buttons[0])
    const id = itemFixture.items[0].evidence_segment_ids[0]
    expect(onSeek).toHaveBeenCalledWith(
      transcriptFixture.segments.find((segment) => segment.id === id)!
        .start_sec,
    )
    expect(screen.getAllByText('Chưa có bằng chứng').length).toBeGreaterThan(0)
  })
  it('renders nullable fields and AI review badges', async () => {
    renderTasks()
    await screen.findByText(itemFixture.items[0].description)
    expect(screen.getByText('Chưa giao')).toBeInTheDocument()
    expect(screen.getByText('Chưa có hạn')).toBeInTheDocument()
    expect(screen.getByText('Cần kiểm tra')).toBeInTheDocument()
    expect(screen.getByText(/Gốc: thứ Sáu tuần này/)).toBeInTheDocument()
  })

  it('creates an item with a speaker and due date', async () => {
    const user = userEvent.setup()
    renderTasks()
    await screen.findByText(itemFixture.items[0].description)
    await user.type(
      screen.getByRole('textbox', { name: 'Thêm nội dung' }),
      'Kiểm tra bản ghi',
    )
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Thêm người nói' }),
      transcriptFixture.speakers[0].id,
    )
    fireEvent.change(screen.getByLabelText('Thêm hạn'), {
      target: { value: '2026-10-30' },
    })
    await user.click(screen.getByRole('button', { name: 'Thêm công việc' }))
    expect(await screen.findByText('Kiểm tra bản ghi')).toBeInTheDocument()
    const items = await listActionItems(meetingFixture.id)
    expect(items.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          description: 'Kiểm tra bản ghi',
          assignee_speaker_id: transcriptFixture.speakers[0].id,
          due_date: '2026-10-30',
          source: 'user',
        }),
      ]),
    )
  })

  it('edits, completes and deletes an item', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderTasks()
    await screen.findByText(itemFixture.items[0].description)
    const id = itemFixture.items[0].id
    await user.click(
      screen.getByRole('button', { name: `Sửa công việc ${id}` }),
    )
    const description = screen.getByRole('textbox', { name: 'Sửa nội dung' })
    await user.clear(description)
    await user.type(description, 'Nội dung đã sửa')
    await user.click(screen.getByRole('button', { name: 'Lưu công việc' }))
    expect(await screen.findByText('Nội dung đã sửa')).toBeInTheDocument()
    await user.click(
      screen.getByRole('checkbox', { name: 'Hoàn thành: Nội dung đã sửa' }),
    )
    expect(
      (await listActionItems(meetingFixture.id)).items?.find(
        (item) => item.id === id,
      )?.status,
    ).toBe('done')
    await user.click(
      screen.getByRole('button', { name: `Xóa công việc ${id}` }),
    )
    expect(await listActionItems(meetingFixture.id)).toMatchObject({
      items: expect.not.arrayContaining([expect.objectContaining({ id })]),
    })
  })

  it('validates description and keeps draft on 409', async () => {
    server.use(
      http.patch('*/api/v1/meetings/:meetingId/action-items/:itemId', () =>
        HttpResponse.json(
          { error: { code: 'VERSION_CONFLICT', message: 'Conflict' } },
          { status: 409 },
        ),
      ),
    )
    const user = userEvent.setup()
    renderTasks()
    await screen.findByText(itemFixture.items[0].description)
    await user.click(
      screen.getByRole('button', {
        name: `Sửa công việc ${itemFixture.items[0].id}`,
      }),
    )
    const description = screen.getByRole('textbox', { name: 'Sửa nội dung' })
    await user.clear(description)
    await user.click(screen.getByRole('button', { name: 'Lưu công việc' }))
    expect(screen.getByRole('alert')).toHaveTextContent('1 đến 1000')
    await user.type(description, 'Bản nháp cần giữ')
    await user.click(screen.getByRole('button', { name: 'Lưu công việc' }))
    expect(await screen.findByRole('alertdialog')).toHaveTextContent('thay đổi')
    expect(description).toHaveValue('Bản nháp cần giữ')
  })
})

it.each(['Thêm', 'Sửa'] as const)(
  'FE-13: dán vượt giới hạn khi %s chỉ gửi nội dung 1000 và người phụ trách 100 ký tự',
  async (prefix) => {
    const lengths: number[][] = []
    const save = async ({ request }: { request: Request }) => {
      const body = (await request.json()) as {
        description: string
        assignee_name: string
      }
      lengths.push([body.description.length, body.assignee_name.length])
      return body.description.length > 1000 || body.assignee_name.length > 100
        ? HttpResponse.json(
            { error: { code: 'VALIDATION_ERROR', message: 'Quá dài' } },
            { status: 422 },
          )
        : HttpResponse.json(
            { ...itemFixture.items[0], ...body },
            { status: prefix === 'Thêm' ? 201 : 200 },
          )
    }
    server.use(
      http.post('*/api/v1/meetings/:id/action-items', save),
      http.patch('*/api/v1/meetings/:id/action-items/:item', save),
    )
    const user = userEvent.setup()
    renderTasks()
    await screen.findByText(itemFixture.items[0].description)
    if (prefix === 'Sửa')
      await user.click(
        screen.getByRole('button', {
          name: `Sửa công việc ${itemFixture.items[0].id}`,
        }),
      )
    const description = screen.getByRole('textbox', {
      name: `${prefix} nội dung`,
    })
    const assignee = screen.getByRole('textbox', {
      name: `${prefix} người phụ trách`,
    })
    await user.clear(description)
    await user.paste('x'.repeat(1001))
    await user.clear(assignee)
    await user.paste('y'.repeat(101))
    await user.click(
      screen.getByRole('button', {
        name: prefix === 'Thêm' ? 'Thêm công việc' : 'Lưu công việc',
      }),
    )
    await waitFor(() => expect(lengths).toEqual([[1000, 100]]))
    expect(description).toHaveAttribute('maxlength', '1000')
    expect(assignee).toHaveAttribute('maxlength', '100')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  },
)
