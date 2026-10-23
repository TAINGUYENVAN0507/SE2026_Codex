import createClient from 'openapi-fetch'
import { ApiError, parseApiError, toNetworkError } from './errors'
import type { components, paths } from './schema'

// Path trong contract đã có /api/v1 nên bỏ tiền tố đó trước khi ghép base URL.
type ApiV1Paths = {
  [
    Path in keyof paths as Path extends `/api/v1${infer Relative}`
      ? Relative
      : never
  ]: paths[Path]
}

export type MeetingDetail = components['schemas']['MeetingDetailOut']
export type Job = components['schemas']['JobOut']
export type MeetingList = components['schemas']['MeetingListOut']
export type TranscriptData = components['schemas']['TranscriptOut']
export type SpeakerData = components['schemas']['SpeakerOut']
export type SegmentData = components['schemas']['TranscriptSegmentOut']

const client = createClient<ApiV1Paths>({
  baseUrl: new URL('/api/v1', window.location.origin).href,
  credentials: 'include',
  fetch: (...args) => globalThis.fetch(...args),
})

client.use({
  async onResponse({ response }) {
    if (!response.ok) throw await parseApiError(response.clone())
  },
})

async function unwrap<T>(
  request: Promise<{
    data?: T
  }>,
): Promise<T> {
  try {
    const { data } = await request
    if (data === undefined)
      throw new ApiError(
        'UNKNOWN_ERROR',
        'Máy chủ trả về dữ liệu không hợp lệ.',
      )
    return data
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw toNetworkError()
  }
}

export function getMeeting(id: MeetingDetail['id']): Promise<MeetingDetail> {
  return unwrap(
    client.GET('/meetings/{meeting_id}', {
      params: { path: { meeting_id: id } },
    }),
  )
}

export function getJob(id: Job['id']): Promise<Job> {
  return unwrap(
    client.GET('/jobs/{job_id}', { params: { path: { job_id: id } } }),
  )
}

export function listMeetings(
  page: number,
  status?: MeetingDetail['status'],
): Promise<MeetingList> {
  return unwrap(
    client.GET('/meetings', { params: { query: { page, status } } }),
  )
}

export function getTranscript(meetingId: string): Promise<TranscriptData> {
  return unwrap(
    client.GET('/meetings/{meeting_id}/transcript', {
      params: { path: { meeting_id: meetingId } },
    }),
  )
}

export function patchSpeaker(
  meetingId: string,
  speakerId: string,
  displayName: string,
  version: number,
): Promise<SpeakerData> {
  return unwrap(
    client.PATCH('/meetings/{meeting_id}/speakers/{speaker_id}', {
      params: { path: { meeting_id: meetingId, speaker_id: speakerId } },
      body: { display_name: displayName, version },
    }),
  )
}

export function patchSegment(
  meetingId: string,
  segmentId: string,
  patch: components['schemas']['SegmentPatch'],
): Promise<SegmentData> {
  return unwrap(
    client.PATCH('/meetings/{meeting_id}/segments/{segment_id}', {
      params: { path: { meeting_id: meetingId, segment_id: segmentId } },
      body: patch,
    }),
  )
}
