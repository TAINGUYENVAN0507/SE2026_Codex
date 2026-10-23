import type { components } from '../../api/schema'
import { ApiError, parseApiError, toNetworkError } from '../../api/errors'

export type UploadForm = {
  title: string
  meetingDate: string
  source: 'upload' | 'recording'
}
export type UploadResult = components['schemas']['MeetingCreateOut']

export function uploadMeeting(
  file: File,
  form: UploadForm,
  key: string,
  onProgress: (percent: number) => void,
) {
  const xhr = new XMLHttpRequest()
  const promise = new Promise<UploadResult>((resolve, reject) => {
    xhr.open('POST', '/api/v1/meetings')
    xhr.withCredentials = true
    xhr.setRequestHeader('Idempotency-Key', key)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0)
        onProgress(
          Math.min(100, Math.round((event.loaded / event.total) * 100)),
        )
    }
    xhr.onabort = () =>
      reject(new ApiError('UPLOAD_CANCELLED', 'Đã hủy tải lên.'))
    xhr.onerror = () => reject(toNetworkError())
    xhr.onload = () => {
      if (xhr.status === 201) {
        try {
          const result = JSON.parse(xhr.responseText) as UploadResult
          if (!result.meeting?.id) throw new Error('Missing meeting ID')
          resolve(result)
        } catch {
          reject(
            new ApiError(
              'UNKNOWN_ERROR',
              'Máy chủ trả về dữ liệu không hợp lệ.',
            ),
          )
        }
      } else {
        void parseApiError(
          new Response(xhr.responseText, { status: xhr.status || 500 }),
        ).then(reject)
      }
    }
    const body = new FormData()
    body.append('file', file)
    body.append('title', form.title)
    body.append('meeting_date', form.meetingDate)
    body.append('source', form.source)
    body.append('consent_confirmed', 'true')
    xhr.send(body)
  })
  return { promise, abort: () => xhr.abort() }
}
