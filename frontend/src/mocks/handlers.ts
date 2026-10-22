import { http, HttpResponse } from 'msw'
import meetingProcessing from '../../../contracts/fixtures/api/meeting_processing.json'
import jobRetryScheduled from '../../../contracts/fixtures/api/job_retry_scheduled.json'
import meetingList from '../../../contracts/fixtures/api/meeting_list.json'
import transcriptReady from '../../../contracts/fixtures/api/transcript_ready.json'
import transcriptPending from '../../../contracts/fixtures/api/transcript_pending.json'
import meetingCreated from '../../../contracts/fixtures/api/meeting_created.json'

type CreatedMeeting = Omit<typeof meetingCreated.meeting, 'duration_sec'> & {
  duration_sec: number | null
}
const createdMeetings = new Map<string, CreatedMeeting>()

function notFound(message: string) {
  return HttpResponse.json(
    { error: { code: 'NOT_FOUND', message, details: null, request_id: null } },
    { status: 404 },
  )
}

export const handlers = [
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
        ? HttpResponse.json(transcriptReady)
        : notFound('Không tìm thấy cuộc họp.'),
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
