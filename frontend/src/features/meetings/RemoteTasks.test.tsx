import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
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

function renderTasks() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const meeting = apiMeetingToView(
    meetingFixture as MeetingDetail,
    transcriptFixture as TranscriptData,
  )
  render(
    <QueryClientProvider client={client}>
      <RemoteTasks meeting={meeting} />
    </QueryClientProvider>,
  )
}

describe('FE-13 action item CRUD', () => {
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
