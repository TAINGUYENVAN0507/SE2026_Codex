export interface UploadConfig {
  max_upload_mb: number
  allowed_extensions: string[]
}

// Giá trị tạm cho bản demo; sẽ được thay bằng GET /api/v1/config khi có API.
export const DEFAULT_UPLOAD_CONFIG: UploadConfig = {
  max_upload_mb: 200,
  allowed_extensions: [
    'mp3',
    'wav',
    'm4a',
    'aac',
    'ogg',
    'opus',
    'webm',
    'mp4',
    'flac',
  ],
}

export function validateAudio(
  file: File,
  config: UploadConfig = DEFAULT_UPLOAD_CONFIG,
): string | null {
  if (!file.size) return 'File đang trống. Hãy chọn một bản ghi khác.'
  if (file.size > config.max_upload_mb * 1024 * 1024)
    return `File vượt quá ${config.max_upload_mb} MB. Hãy chọn một bản ghi nhỏ hơn.`
  const extension = file.name.split('.').pop()?.toLowerCase()
  const allowed = config.allowed_extensions.map((item) =>
    item.replace(/^\./, '').toLowerCase(),
  )
  if (!extension || !allowed.includes(extension))
    return `Định dạng chưa hỗ trợ. Các định dạng được phép: ${allowed.map((item) => item.toUpperCase()).join(', ')}.`
  return null
}
