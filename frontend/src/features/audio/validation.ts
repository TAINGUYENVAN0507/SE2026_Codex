export const MAX_AUDIO_BYTES = 200 * 1024 * 1024
export function validateAudio(file: File): string | null {
  if (!file.size) return 'File đang trống. Hãy chọn một bản ghi khác.'
  if (file.size > MAX_AUDIO_BYTES)
    return 'File vượt quá 200 MB. Hãy chọn một bản ghi nhỏ hơn.'
  if (!/\.(mp3|wav|m4a|aac|ogg|opus|webm|mp4|flac)$/i.test(file.name))
    return 'Định dạng chưa hỗ trợ. Hãy chọn file audio MP3, WAV, M4A, OGG hoặc WebM.'
  return null
}
