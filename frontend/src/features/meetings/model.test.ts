import { describe, expect, it } from 'vitest'
import { exportMeeting, formatTime, seedMeetings } from './model'
import { DEFAULT_UPLOAD_CONFIG, validateAudio } from '../audio/validation'

describe('meeting exports and audio validation', () => {
  it('exports current edits and unknown assignees/deadlines', () => {
    const meeting = seedMeetings()[0]
    meeting.segments[0].text = 'Nội dung đã chỉnh sửa'
    meeting.tasks.push({
      id: 'new',
      text: 'Việc mới',
      assignee: '',
      dueDate: '',
      done: false,
    })
    expect(exportMeeting(meeting, 'txt')).toContain('Nội dung đã chỉnh sửa')
    expect(exportMeeting(meeting, 'md')).toContain('Chưa giao · Chưa có hạn')
    expect(
      JSON.parse(exportMeeting(meeting, 'json')).meeting.segments[0].text,
    ).toBe('Nội dung đã chỉnh sửa')
    expect(exportMeeting(meeting, 'json')).toBe(exportMeeting(meeting, 'json'))
  })
  it('formats long recordings without losing hours', () => {
    expect(formatTime(0)).toBe('00:00')
    expect(formatTime(255)).toBe('04:15')
    expect(formatTime(3661)).toBe('1:01:01')
  })
  it('rejects empty, oversized and unsupported files', () => {
    expect(validateAudio(new File([], 'empty.mp3'))).toContain('trống')
    const large = new File(['a'], 'large.mp3')
    Object.defineProperty(large, 'size', {
      value: DEFAULT_UPLOAD_CONFIG.max_upload_mb * 1024 * 1024 + 1,
    })
    expect(validateAudio(large)).toContain('200 MB')
    expect(validateAudio(new File(['audio'], 'meeting.WAV'))).toBeNull()
  })
})
