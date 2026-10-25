import { notifyNetworkFailure } from './networkEvents'

export type ApiErrorCode =
  | 'FILE_TOO_LARGE'
  | 'UNSUPPORTED_MEDIA_TYPE'
  | 'AUDIO_INVALID'
  | 'AUDIO_TOO_SHORT'
  | 'AUDIO_TOO_LONG'
  | 'CONSENT_REQUIRED'
  | 'VERSION_CONFLICT'
  | 'UNAUTHENTICATED'
  | 'NETWORK_ERROR'
  | 'UNKNOWN_ERROR'
  | (string & {})

export type ApiErrorDetails = Record<string, unknown> | null

const messages: Record<string, string> = {
  BAD_REQUEST: 'Yêu cầu không hợp lệ. Hãy kiểm tra thông tin rồi thử lại.',
  IDEMPOTENCY_KEY_REQUIRED: 'Thiếu khóa chống gửi trùng. Hãy thử lại.',
  CONFLICT: 'Yêu cầu xung đột với dữ liệu hiện tại. Hãy thử lại.',
  FILE_TOO_LARGE: 'File audio vượt quá dung lượng cho phép.',
  UNSUPPORTED_MEDIA_TYPE: 'Định dạng file audio chưa được hỗ trợ.',
  AUDIO_INVALID: 'File audio không hợp lệ hoặc không thể đọc.',
  AUDIO_TOO_SHORT: 'File audio quá ngắn để xử lý.',
  AUDIO_TOO_LONG: 'File audio vượt quá thời lượng cho phép.',
  CONSENT_REQUIRED: 'Cần xác nhận sự đồng ý trước khi tiếp tục.',
  SPEAKER_NAME_DUPLICATE: 'Tên người nói đã được sử dụng. Hãy chọn tên khác.',
  VERSION_CONFLICT:
    'Dữ liệu đã được thay đổi ở nơi khác. Hãy tải lại rồi thử lại.',
  UNAUTHENTICATED: 'Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.',
  INVALID_CREDENTIALS: 'Email hoặc mật khẩu không chính xác.',
  NOT_FOUND: 'Không tìm thấy dữ liệu yêu cầu.',
  MEETING_NOT_FOUND: 'Không tìm thấy cuộc họp.',
  TRANSCRIPT_NOT_READY: 'Transcript chưa sẵn sàng để xuất.',
  VALIDATION_ERROR: 'Thông tin chưa hợp lệ. Hãy kiểm tra rồi thử lại.',
  NETWORK_ERROR: 'Không thể kết nối máy chủ. Hãy kiểm tra mạng rồi thử lại.',
  UNKNOWN_ERROR: 'Đã xảy ra lỗi không xác định. Hãy thử lại sau.',
}

export class ApiError extends Error {
  readonly code: ApiErrorCode
  readonly details: ApiErrorDetails
  readonly request_id: string | null
  readonly status: number

  constructor(
    code: ApiErrorCode,
    message: string,
    details: ApiErrorDetails = null,
    requestId: string | null = null,
    status = 0,
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.details = details
    this.request_id = requestId
    this.status = status
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export async function parseApiError(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json()
    if (!isRecord(body) || !isRecord(body.error))
      return new ApiError(
        'UNKNOWN_ERROR',
        messages.UNKNOWN_ERROR,
        null,
        null,
        response.status,
      )

    const { code, message, details, request_id: requestId } = body.error
    if (typeof code !== 'string' || typeof message !== 'string')
      return new ApiError(
        'UNKNOWN_ERROR',
        messages.UNKNOWN_ERROR,
        null,
        null,
        response.status,
      )

    return new ApiError(
      code,
      messages[code] ?? messages.UNKNOWN_ERROR,
      isRecord(details) ? details : null,
      typeof requestId === 'string' ? requestId : null,
      response.status,
    )
  } catch {
    return new ApiError(
      'UNKNOWN_ERROR',
      messages.UNKNOWN_ERROR,
      null,
      null,
      response.status,
    )
  }
}

export function toNetworkError(): ApiError {
  notifyNetworkFailure()
  return new ApiError('NETWORK_ERROR', messages.NETWORK_ERROR)
}
