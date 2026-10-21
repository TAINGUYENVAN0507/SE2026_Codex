import { describe, expect, it } from 'vitest'
import { validateAudio, type UploadConfig } from './validation'

const config: UploadConfig = {
  max_upload_mb: 1,
  allowed_extensions: ['mp3', '.wav'],
}

describe('validateAudio', () => {
  it('rejects an empty file', () => {
    expect(validateAudio(new File([], 'empty.mp3'), config)).toContain('trống')
  })

  it('reports the configured size limit', () => {
    const file = new File(['a'], 'large.mp3')
    Object.defineProperty(file, 'size', { value: 1024 * 1024 + 1 })
    expect(validateAudio(file, config)).toContain('1 MB')
  })

  it('rejects an extension outside the config', () => {
    expect(validateAudio(new File(['audio'], 'meeting.ogg'), config)).toContain(
      'Định dạng chưa hỗ trợ',
    )
  })

  it('accepts configured extensions regardless of letter case', () => {
    expect(validateAudio(new File(['audio'], 'meeting.WAV'), config)).toBeNull()
  })

  it('accepts a file within the configured limit', () => {
    expect(validateAudio(new File(['audio'], 'meeting.mp3'), config)).toBeNull()
  })
})
