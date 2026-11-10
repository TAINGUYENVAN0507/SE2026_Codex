import { retryAfterMs } from './retryAfter'
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
  AUDIO_EXPIRED: 'Audio đã hết hạn lưu trữ. Bạn vẫn có thể đọc transcript.',
  DIARIZATION_FAILED:
    'Chưa phân biệt được người nói. Hãy kiểm tra và đặt tên người nói trong transcript.',
  FORBIDDEN: 'Bạn không có quyền thực hiện thao tác này.',
  FORMAT_NOT_SUPPORTED:
    'Định dạng xuất chưa được hỗ trợ. Hãy chọn TXT, Markdown hoặc JSON.',
  HAS_USER_EDITS:
    'Nội dung đã được chỉnh sửa. Hãy xác nhận trước khi xử lý lại.',
  HTTP_ERROR: 'Yêu cầu chưa được máy chủ xử lý. Hãy thử lại sau.',
  INTERNAL_ERROR: 'Bước xử lý gặp lỗi nội bộ. Hãy thử xử lý lại.',
  INTERNAL_SERVER_ERROR: 'Máy chủ gặp lỗi nội bộ. Hãy thử lại sau.',
  JOB_ALREADY_ACTIVE:
    'Cuộc họp đang được xử lý. Hãy theo dõi tiến độ hiện tại.',
  JOB_ALREADY_SUCCEEDED: 'Lượt xử lý này đã hoàn tất. Hãy mở kết quả cuộc họp.',
  LEASE_TIMEOUT: 'Lượt xử lý bị gián đoạn quá lâu. Hãy thử xử lý lại.',
  LLM_OUTPUT_INVALID:
    'Kết quả tóm tắt chưa đúng định dạng. Hãy thử tạo lại tóm tắt.',
  LLM_UNAVAILABLE:
    'Dịch vụ tóm tắt tạm thời không phản hồi. Hãy theo dõi tiến độ thử lại.',
  METHOD_NOT_ALLOWED: 'Thao tác này chưa được hỗ trợ trên máy chủ hiện tại.',
  MISSING_INPUT:
    'Thiếu dữ liệu cho bước xử lý tiếp theo. Hãy kiểm tra bản ghi và thử lại.',
  MODEL_UNAVAILABLE: 'Mô hình xử lý audio chưa sẵn sàng. Hãy thử lại sau.',
  PIPELINE_CANCELLED: 'Quá trình xử lý cuộc họp đã bị hủy.',
  PIPELINE_OUTPUT_INVALID: 'Kết quả xử lý chưa hợp lệ. Hãy thử xử lý lại.',
  RANGE_NOT_SATISFIABLE: 'Mốc audio nằm ngoài bản ghi. Hãy chọn một mốc khác.',
  REQUEST_IN_PROGRESS:
    'Yêu cầu trước đang được xử lý. Hãy chờ kết quả trước khi gửi lại.',
  SERVICE_UNAVAILABLE: 'Máy chủ đang bận. Vui lòng thử lại sau.',
  SPEAKER_NOT_IN_MEETING:
    'Người nói không thuộc cuộc họp này. Hãy chọn lại người nói.',
  STAGE_CRASHED: 'Một bước xử lý bị dừng đột ngột. Hãy thử xử lý lại.',
  STAGE_NOT_IMPLEMENTED: 'Bước xử lý này hiện chưa được hỗ trợ.',
  STAGE_TIMEOUT: 'Một bước xử lý quá thời gian cho phép. Hãy thử xử lý lại.',
  TEXT_EMPTY: 'Nội dung không được để trống.',
  TEXT_TOO_LONG: 'Nội dung vượt quá độ dài cho phép. Hãy rút gọn rồi lưu lại.',
  UNPROCESSABLE_ENTITY:
    'Dữ liệu gửi lên chưa hợp lệ. Hãy kiểm tra các trường rồi thử lại.',

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
  NO_SPEECH_DETECTED: 'Không phát hiện lời nói trong bản ghi.',
  OUT_OF_MEMORY:
    'Hệ thống không đủ tài nguyên để xử lý bản ghi. Hãy thử lại sau.',
  LLM_REQUEST_INVALID:
    'Chưa thể tạo tóm tắt. Bạn vẫn có thể đọc và sửa transcript.',
  VALIDATION_ERROR: 'Thông tin chưa hợp lệ. Hãy kiểm tra rồi thử lại.',
  NETWORK_ERROR: 'Không thể kết nối máy chủ. Hãy kiểm tra mạng rồi thử lại.',
  UNKNOWN_ERROR: 'Đã xảy ra lỗi không xác định. Hãy thử lại sau.',
}

export function errorMessageForCode(code: string): string {
  return messages[code] ?? messages.UNKNOWN_ERROR
}

export class ApiError extends Error {
  readonly code: ApiErrorCode
  readonly details: ApiErrorDetails
  readonly request_id: string | null
  readonly status: number
  readonly retryAfterMs: number | null

  constructor(
    code: ApiErrorCode,
    message: string,
    details: ApiErrorDetails = null,
    requestId: string | null = null,
    status = 0,
    retryAfter: number | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.details = details
    this.request_id = requestId
    this.status = status
    this.retryAfterMs = retryAfter
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
        retryAfterMs(response.headers.get('Retry-After')),
      )

    const { code, message, details, request_id: requestId } = body.error
    if (typeof code !== 'string' || typeof message !== 'string')
      return new ApiError(
        'UNKNOWN_ERROR',
        messages.UNKNOWN_ERROR,
        null,
        null,
        response.status,
        retryAfterMs(response.headers.get('Retry-After')),
      )

    return new ApiError(
      code,
      messages[code] ?? messages.UNKNOWN_ERROR,
      isRecord(details) ? details : null,
      typeof requestId === 'string' ? requestId : null,
      response.status,
      retryAfterMs(response.headers.get('Retry-After')),
    )
  } catch {
    return new ApiError(
      'UNKNOWN_ERROR',
      messages.UNKNOWN_ERROR,
      null,
      null,
      response.status,
      retryAfterMs(response.headers.get('Retry-After')),
    )
  }
}

export function toNetworkError(): ApiError {
  notifyNetworkFailure()
  return new ApiError('NETWORK_ERROR', messages.NETWORK_ERROR)
}

export function isServiceBusy(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 503
}
