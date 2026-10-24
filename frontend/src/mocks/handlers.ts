import { http, HttpResponse } from 'msw'
import meetingProcessing from '../../../contracts/fixtures/api/meeting_processing.json'
import jobRetryScheduled from '../../../contracts/fixtures/api/job_retry_scheduled.json'
import meetingList from '../../../contracts/fixtures/api/meeting_list.json'
import transcriptReady from '../../../contracts/fixtures/api/transcript_ready.json'
import transcriptPending from '../../../contracts/fixtures/api/transcript_pending.json'
import meetingCreated from '../../../contracts/fixtures/api/meeting_created.json'
import summaryReady from '../../../contracts/fixtures/api/summary_ready.json'
import summaryDisabled from '../../../contracts/fixtures/api/summary_disabled.json'
import actionItems from '../../../contracts/fixtures/api/action_items.json'
import type { ActionItemData, SegmentData, SummaryData } from '../api/client'
import { authHandlers } from './auth'

type CreatedMeeting = Omit<typeof meetingCreated.meeting, 'duration_sec'> & {
  duration_sec: number | null
}
const createdMeetings = new Map<string, CreatedMeeting>()
const editedSegments = new Map<string, SegmentData>()
let editedSummary: SummaryData | null = null
const mockActionItems = new Map<string, ActionItemData>()

function resetMockActionItems() {
  mockActionItems.clear()
  for (const item of actionItems.items)
    mockActionItems.set(item.id, item as ActionItemData)
}
resetMockActionItems()

export function resetMockMeetings() {
  createdMeetings.clear()
  editedSegments.clear()
  editedSummary = null
  resetMockActionItems()
}

function notFound(message: string) {
  return HttpResponse.json(
    { error: { code: 'NOT_FOUND', message, details: null, request_id: null } },
    { status: 404 },
  )
}

export const handlers = [
  ...authHandlers,
  http.post('*/api/v1/meetings', async ({ request }) => {
    const form = await request.formData()
    const id = crypto.randomUUID()
    const created = {
      ...meetingCreated.meeting,
      id,
      title: String(form.get('title') || meetingCreated.meeting.title),
      meeting_date: String(
        form.get('meeting_date') || meetingCreated.meeting.meeting_date,
      ),
      source: String(form.get('source') || 'upload'),
      duration_sec: null,
    }
    createdMeetings.set(id, created)
    return HttpResponse.json(
      { ...meetingCreated, meeting: created },
      { status: 201 },
    )
  }),
  http.get('*/api/v1/meetings', ({ request }) => {
    const url = new URL(request.url)
    const page = Number(url.searchParams.get('page') || 1)
    const status = url.searchParams.get('status')
    const allItems = [...createdMeetings.values(), ...meetingList.items]
    const items = status
      ? allItems.filter((item) => item.status === status)
      : allItems
    return HttpResponse.json({
      items: items.slice((page - 1) * 10, page * 10),
      page,
      page_size: 10,
      total: items.length,
    })
  }),
  http.get('*/api/v1/meetings/:meetingId', ({ params }) => {
    const created = createdMeetings.get(String(params.meetingId))
    if (created) return HttpResponse.json(created)
    return params.meetingId === meetingProcessing.id
      ? HttpResponse.json(meetingProcessing)
      : notFound('Không tìm thấy cuộc họp.')
  }),
  http.get('*/api/v1/meetings/:meetingId/transcript', ({ params }) =>
    createdMeetings.has(String(params.meetingId))
      ? HttpResponse.json(transcriptPending)
      : params.meetingId === meetingProcessing.id
        ? HttpResponse.json({
            ...transcriptReady,
            segments: transcriptReady.segments.map(
              (segment) => editedSegments.get(segment.id) ?? segment,
            ),
          })
        : notFound('Không tìm thấy cuộc họp.'),
  ),
  http.get('*/api/v1/meetings/:meetingId/summary', ({ params }) =>
    params.meetingId === meetingProcessing.id
      ? HttpResponse.json(editedSummary ?? summaryReady)
      : createdMeetings.has(String(params.meetingId))
        ? HttpResponse.json(summaryDisabled)
        : notFound('Không tìm thấy tóm tắt.'),
  ),
  http.put(
    '*/api/v1/meetings/:meetingId/summary',
    async ({ params, request }) => {
      if (params.meetingId !== meetingProcessing.id)
        return notFound('Không tìm thấy tóm tắt.')
      const body = (await request.json()) as {
        content: typeof summaryReady.content
        version: number
      }
      const current = editedSummary ?? summaryReady
      if (body.version !== current.version)
        return HttpResponse.json(
          {
            error: {
              code: 'VERSION_CONFLICT',
              message: 'Tóm tắt đã được thay đổi.',
              details: { current },
              request_id: null,
            },
          },
          { status: 409 },
        )
      editedSummary = {
        ...current,
        content: body.content,
        is_edited: true,
        version: current.version + 1,
      }
      return HttpResponse.json(editedSummary)
    },
  ),
  http.post(
    '*/api/v1/meetings/:meetingId/jobs',
    async ({ params, request }) => {
      if (params.meetingId !== meetingProcessing.id)
        return notFound('Không tìm thấy cuộc họp.')
      const body = (await request.json()) as { from_stage?: string }
      if (body.from_stage !== 'summarize')
        return HttpResponse.json(
          { error: { code: 'BAD_REQUEST', message: 'Stage không hợp lệ.' } },
          { status: 400 },
        )
      editedSummary = { ...summaryReady, status: 'pending', content: null }
      return HttpResponse.json(
        { ...jobRetryScheduled, status: 'queued' },
        { status: 202 },
      )
    },
  ),
  http.get('*/api/v1/meetings/:meetingId/action-items', ({ params }) =>
    params.meetingId === meetingProcessing.id
      ? HttpResponse.json({ items: [...mockActionItems.values()] })
      : notFound('Không tìm thấy cuộc họp.'),
  ),
  http.post(
    '*/api/v1/meetings/:meetingId/action-items',
    async ({ params, request }) => {
      if (params.meetingId !== meetingProcessing.id)
        return notFound('Không tìm thấy cuộc họp.')
      const body = (await request.json()) as {
        description: string
        assignee_name?: string | null
        assignee_speaker_id?: string | null
        due_date?: string | null
        status: string
      }
      if (!body.description.trim() || body.description.trim().length > 1000)
        return HttpResponse.json(
          {
            error: { code: 'VALIDATION_ERROR', message: 'Mô tả không hợp lệ.' },
          },
          { status: 422 },
        )
      const now = new Date().toISOString()
      const item: ActionItemData = {
        id: crypto.randomUUID(),
        meeting_id: meetingProcessing.id,
        description: body.description.trim(),
        assignee_name: body.assignee_name ?? null,
        assignee_speaker_id: body.assignee_speaker_id ?? null,
        due_date: body.due_date ?? null,
        due_date_text: null,
        status: body.status,
        source: 'user',
        is_edited: false,
        needs_review: false,
        evidence_segment_ids: [],
        ai_original: null,
        version: 1,
        created_at: now,
        updated_at: now,
      }
      mockActionItems.set(item.id, item)
      return HttpResponse.json(item, { status: 201 })
    },
  ),
  http.patch(
    '*/api/v1/meetings/:meetingId/action-items/:itemId',
    async ({ params, request }) => {
      const current = mockActionItems.get(String(params.itemId))
      if (!current || params.meetingId !== meetingProcessing.id)
        return notFound('Không tìm thấy công việc.')
      const body = (await request.json()) as {
        description?: string
        assignee_name?: string | null
        assignee_speaker_id?: string | null
        due_date?: string | null
        status?: string
        version: number
      }
      if (body.version !== current.version)
        return HttpResponse.json(
          { error: { code: 'VERSION_CONFLICT', message: 'Công việc đã đổi.' } },
          { status: 409 },
        )
      const saved: ActionItemData = {
        ...current,
        description: body.description ?? current.description,
        assignee_name:
          body.assignee_name === undefined
            ? current.assignee_name
            : body.assignee_name,
        assignee_speaker_id:
          body.assignee_speaker_id === undefined
            ? current.assignee_speaker_id
            : body.assignee_speaker_id,
        due_date:
          body.due_date === undefined ? current.due_date : body.due_date,
        status: body.status ?? current.status,
        is_edited: true,
        version: current.version + 1,
      }
      mockActionItems.set(saved.id, saved)
      return HttpResponse.json(saved)
    },
  ),
  http.delete(
    '*/api/v1/meetings/:meetingId/action-items/:itemId',
    ({ params, request }) => {
      const current = mockActionItems.get(String(params.itemId))
      if (!current || params.meetingId !== meetingProcessing.id)
        return notFound('Không tìm thấy công việc.')
      const version = Number(new URL(request.url).searchParams.get('version'))
      if (version !== current.version)
        return HttpResponse.json(
          { error: { code: 'VERSION_CONFLICT', message: 'Công việc đã đổi.' } },
          { status: 409 },
        )
      mockActionItems.delete(current.id)
      return new HttpResponse(null, { status: 204 })
    },
  ),
  http.patch(
    '*/api/v1/meetings/:meetingId/segments/:segmentId',
    async ({ params, request }) => {
      if (params.meetingId !== meetingProcessing.id)
        return notFound('Không tìm thấy cuộc họp.')
      const original = transcriptReady.segments.find(
        (item) => item.id === params.segmentId,
      )
      if (!original) return notFound('Không tìm thấy đoạn transcript.')
      const current = editedSegments.get(original.id) ?? original
      const body = (await request.json()) as {
        text?: string
        speaker_id?: string | null
        version: number
      }
      if (body.version !== current.version)
        return HttpResponse.json(
          {
            error: {
              code: 'VERSION_CONFLICT',
              message: 'Đoạn transcript đã thay đổi.',
              details: { current },
              request_id: null,
            },
          },
          { status: 409 },
        )
      if (
        body.text !== undefined &&
        (body.text.trim().length < 1 || body.text.trim().length > 5000)
      )
        return HttpResponse.json(
          {
            error: {
              code: 'VALIDATION_ERROR',
              message: 'Nội dung cần có từ 1 đến 5000 ký tự.',
              details: null,
              request_id: null,
            },
          },
          { status: 422 },
        )
      const saved = {
        ...current,
        text: body.text?.trim() ?? current.text,
        speaker_id:
          body.speaker_id === undefined ? current.speaker_id : body.speaker_id,
        is_edited:
          (body.text?.trim() ?? current.text) !== current.ai_text ||
          (body.speaker_id === undefined
            ? current.speaker_id
            : body.speaker_id) !== current.ai_speaker_id,
        version: current.version + 1,
      }
      editedSegments.set(original.id, saved)
      return HttpResponse.json(saved)
    },
  ),
  http.patch(
    '*/api/v1/meetings/:meetingId/speakers/:speakerId',
    async ({ params, request }) => {
      const speaker = transcriptReady.speakers.find(
        (item) => item.id === params.speakerId,
      )
      if (!speaker) return notFound('Không tìm thấy người nói.')
      const body = (await request.json()) as {
        display_name: string
        version: number
      }
      if (
        transcriptReady.speakers.some(
          (item) =>
            item.id !== speaker.id && item.display_name === body.display_name,
        )
      )
        return HttpResponse.json(
          {
            error: {
              code: 'SPEAKER_NAME_DUPLICATE',
              message: 'Tên người nói đã được sử dụng.',
              details: null,
              request_id: null,
            },
          },
          { status: 422 },
        )
      if (body.version !== speaker.version)
        return HttpResponse.json(
          {
            error: {
              code: 'VERSION_CONFLICT',
              message: 'Dữ liệu đã thay đổi.',
              details: null,
              request_id: null,
            },
          },
          { status: 409 },
        )
      return HttpResponse.json({
        ...speaker,
        display_name: body.display_name,
        version: speaker.version + 1,
      })
    },
  ),
  http.get('*/api/v1/jobs/:jobId', ({ params }) =>
    params.jobId === jobRetryScheduled.id
      ? HttpResponse.json(jobRetryScheduled)
      : notFound('Không tìm thấy job.'),
  ),
]
