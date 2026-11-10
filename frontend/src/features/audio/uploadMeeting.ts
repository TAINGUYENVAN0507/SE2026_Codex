import type { components } from '../../api/schema'
import { ApiError, parseApiError, toNetworkError } from '../../api/errors'
import { notifySessionExpired } from '../../api/sessionEvents'

export type UploadForm = {
  title: string
  meetingDate: string
  source: 'upload' | 'recording'
}
export type UploadResult = components['schemas']['MeetingCreateOut']
const MAX_BUSY_RETRIES = 3
const DEFAULT_BUSY_WAIT_MS = 2_000

export function uploadMeeting(
  file: File,
  form: UploadForm,
  key: string,
  onProgress: (percent: number) => void,
  onBusy?: (retry: number, waitMs: number) => void,
) {
  let current: XMLHttpRequest | null = null
  let timer: ReturnType<typeof setTimeout> | undefined
  let finished = false
  let retries = 0
  let rejectUpload!: (error: ApiError) => void
  const promise = new Promise<UploadResult>((resolve, reject) => {
    rejectUpload = reject
    function fail(error: ApiError) {
      if (finished) return
      finished = true
      reject(error)
    }
    function send() {
      if (finished) return
      const xhr = new XMLHttpRequest()
      current = xhr
      xhr.open('POST', '/api/v1/meetings')
      xhr.withCredentials = true
      xhr.setRequestHeader('Idempotency-Key', key)
      xhr.upload.onprogress = (event) => {
        if (!finished && event.lengthComputable && event.total > 0)
          onProgress(
            Math.min(100, Math.round((event.loaded / event.total) * 100)),
          )
      }
      xhr.onabort = () =>
        fail(new ApiError('UPLOAD_CANCELLED', 'Đã hủy tải lên.'))
      xhr.onerror = () => fail(toNetworkError())
      xhr.onload = async () => {
        if (finished) return
        if (xhr.status === 401) notifySessionExpired()
        if (xhr.status === 201) {
          try {
            const result = JSON.parse(xhr.responseText) as UploadResult
            if (!result.meeting?.id) throw new Error('Missing meeting ID')
            finished = true
            resolve(result)
          } catch {
            fail(
              new ApiError(
                'UNKNOWN_ERROR',
                'Máy chủ trả về dữ liệu không hợp lệ.',
              ),
            )
          }
          return
        }
        const error = await parseApiError(
          new Response(xhr.responseText, {
            status: xhr.status || 500,
            headers: {
              'Retry-After': xhr.getResponseHeader?.('Retry-After') || '',
            },
          }),
        )
        if (finished) return
        if (
          error.status === 503 &&
          error.code === 'SERVICE_UNAVAILABLE' &&
          retries < MAX_BUSY_RETRIES
        ) {
          const wait = error.retryAfterMs ?? DEFAULT_BUSY_WAIT_MS
          retries++
          onBusy?.(retries, wait)
          timer = setTimeout(() => {
            onProgress(0)
            send()
          }, wait)
        } else fail(error)
      }
      const body = new FormData()
      body.append('file', file)
      body.append('title', form.title)
      body.append('meeting_date', form.meetingDate)
      body.append('source', form.source)
      body.append('consent_confirmed', 'true')
      xhr.send(body)
    }
    send()
  })
  return {
    promise,
    abort: () => {
      if (finished) return
      finished = true
      clearTimeout(timer)
      current?.abort()
      rejectUpload(new ApiError('UPLOAD_CANCELLED', 'Đã hủy tải lên.'))
    },
  }
}
