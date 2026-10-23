import type { MeetingDetail, TranscriptData } from '../../api/client'
import { initials, type Meeting } from './model'

export function apiMeetingToView(
  meeting: MeetingDetail,
  transcript: TranscriptData,
): Meeting {
  return {
    id: meeting.id,
    title: meeting.title,
    date: meeting.meeting_date || meeting.created_at.slice(0, 10),
    time: new Date(meeting.created_at).toLocaleTimeString('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
    }),
    duration: meeting.duration_sec || 0,
    status:
      meeting.status === 'queued'
        ? 'pending'
        : meeting.status === 'partial'
          ? 'ready'
          : meeting.status,
    speakers: (transcript.speakers || []).map((speaker) => ({
      id: speaker.id,
      name: speaker.display_name,
      initials: initials(speaker.display_name),
      version: speaker.version,
      colorIndex: speaker.color_index,
    })),
    segments: (transcript.segments || [])
      .sort((a, b) => a.start_sec - b.start_sec)
      .map((segment) => ({
        id: segment.id,
        start: segment.start_sec,
        end: segment.end_sec,
        speakerId: segment.speaker_id ?? null,
        text: segment.text,
        originalText: segment.ai_text,
        edited: segment.is_edited || false,
        flags: segment.flags || [],
      })),
    overview: '',
    points: [],
    decisions: [],
    tasks: [],
  }
}
