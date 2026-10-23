export type MeetingStatus = 'ready' | 'processing' | 'failed' | 'pending'

export interface Speaker {
  id: string
  name: string
  initials: string
  version?: number
  colorIndex?: number
}
export interface Segment {
  id: string
  start: number
  end: number
  speakerId: string | null
  text: string
  originalText: string
  edited: boolean
  flags?: string[]
}
export interface Task {
  id: string
  text: string
  assignee: string
  dueDate: string
  done: boolean
}
export interface Evidence {
  text: string
  segmentId: string
}
export interface Meeting {
  id: string
  title: string
  date: string
  time: string
  duration: number
  status: MeetingStatus
  speakers: Speaker[]
  segments: Segment[]
  overview: string
  points: Evidence[]
  decisions: Evidence[]
  tasks: Task[]
  fileName?: string
}

export const DEMO_ID = 'sprint-42'
const speakers: Speaker[] = [
  { id: 'vt', name: 'Văn Tường', initials: 'VT' },
  { id: 'mq', name: 'Minh Quang', initials: 'MQ' },
  { id: 'nt', name: 'Nguyên Tài', initials: 'NT' },
]
const turns = [
  [
    'vt',
    0,
    80,
    'Chào mọi người, hôm nay chúng ta chốt phạm vi sprint 42. Mục tiêu là hoàn thiện luồng biên bản cuộc họp tiếng Việt: từ tải file audio, xem và chỉnh sửa transcript đến xuất biên bản.',
  ],
  [
    'mq',
    88,
    170,
    'Phần backend đã có bản thiết kế API upload và hàng đợi xử lý. Mình sẽ thống nhất cấu trúc dữ liệu với Tường để giao diện nhận được tiến độ và hiển thị kết quả ngay khi transcript sẵn sàng.',
  ],
  [
    'nt',
    255,
    345,
    'Về pipeline, mình sẽ kiểm tra nhận dạng tiếng Việt và phân biệt người nói trên audio thử nghiệm. Nếu tóm tắt chưa xong thì mọi người vẫn có thể nghe lại và chỉnh sửa transcript trước.',
  ],
  [
    'vt',
    455,
    550,
    'Thống nhất nhé. Mình phụ trách giao diện, player và chỉnh sửa inline. Quang hoàn thiện API upload trước ngày 22/10. Tài chuẩn bị audio kiểm thử có sự đồng ý của người tham gia.',
  ],
  [
    'mq',
    620,
    720,
    'Được, mình sẽ gửi OpenAPI và dữ liệu mẫu trước để frontend làm song song. Khi nối API thật, cả nhóm cùng kiểm tra upload, trạng thái xử lý và xuất biên bản.',
  ],
  [
    'nt',
    940,
    1030,
    'Phần DOCX mình để sau MVP nhé. Trước mắt giữ TXT, JSON và Markdown. Các kết quả nhận dạng chưa chắc chắn cần có dấu hiệu để người dùng nghe lại.',
  ],
  [
    'vt',
    1320,
    1395,
    'Vậy thứ Sáu mình demo luồng chính cùng nhau. Ưu tiên thao tác rõ ràng và xử lý lỗi đầy đủ, sau đó mới thêm các phần nâng cao.',
  ],
] as const

const demo: Meeting = {
  id: DEMO_ID,
  title: 'Họp kế hoạch sprint 42',
  date: '2026-10-18',
  time: '09:30',
  duration: 1720,
  status: 'ready',
  speakers,
  segments: turns.map(([speakerId, start, end, text], i) => ({
    id: `s${i}`,
    start,
    end,
    speakerId,
    text,
    originalText: text,
    edited: false,
  })),
  overview:
    'Nhóm thống nhất phạm vi sprint 42: hoàn thiện luồng tải audio, transcript có thể chỉnh sửa và xuất biên bản. Frontend, backend và pipeline được phát triển song song thông qua contract và dữ liệu mẫu.',
  points: [
    {
      text: 'Giao diện ưu tiên trải nghiệm nghe, đọc và chỉnh sửa transcript trong cùng một màn hình.',
      segmentId: 's3',
    },
    {
      text: 'Backend cung cấp OpenAPI và fixtures để frontend phát triển song song.',
      segmentId: 's4',
    },
    {
      text: 'Transcript có thể xem và chỉnh sửa trong lúc chờ bản tóm tắt.',
      segmentId: 's2',
    },
  ],
  decisions: [
    {
      text: 'Giữ ba định dạng xuất: TXT, JSON và Markdown. DOCX chuyển sang sau MVP.',
      segmentId: 's5',
    },
    {
      text: 'Demo chung luồng chính vào thứ Sáu, sau khi hoàn thiện các trường hợp lỗi.',
      segmentId: 's6',
    },
  ],
  tasks: [
    {
      id: 't1',
      text: 'Hoàn thiện giao diện transcript và player',
      assignee: 'Văn Tường',
      dueDate: '2026-10-22',
      done: false,
    },
    {
      id: 't2',
      text: 'Chốt OpenAPI và API upload audio',
      assignee: 'Minh Quang',
      dueDate: '2026-10-22',
      done: false,
    },
    {
      id: 't3',
      text: 'Chuẩn bị audio thử nghiệm có consent',
      assignee: 'Nguyên Tài',
      dueDate: '',
      done: false,
    },
  ],
  fileName: 'Sprint_42_Audio.mp3',
}

export function seedMeetings(): Meeting[] {
  const rows = [
    [
      'interview',
      'Phỏng vấn người dùng: trải nghiệm xuất biên bản',
      '2026-10-17',
      '14:15',
      2700,
      'ready',
    ],
    [
      'technical',
      'Giao ban đầu tuần phòng Kỹ thuật',
      '2026-10-16',
      '08:00',
      1080,
      'processing',
    ],
    [
      'architecture',
      'Thảo luận kiến trúc lưu trữ audio',
      '2026-10-15',
      '16:00',
      3120,
      'ready',
    ],
    ['daily', 'Daily Scrum: ngày 14/10', '2026-10-14', '09:15', 840, 'ready'],
    ['draft', 'Ghi âm nháp phòng họp A3', '2026-10-12', '11:00', 300, 'failed'],
  ] as const
  return [
    structuredClone(demo),
    ...rows.map(([id, title, date, time, duration, status]) => ({
      id,
      title,
      date,
      time,
      duration,
      status,
      speakers: [],
      segments: [],
      overview: '',
      points: [],
      decisions: [],
      tasks: [],
    })),
  ]
}

export function formatTime(value: number) {
  const total = Math.max(0, Math.floor(Number.isFinite(value) ? value : 0))
  const hours = Math.floor(total / 3600)
  return `${hours ? `${hours}:` : ''}${String(Math.floor(total / 60) % 60).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}
export function formatDate(date: string) {
  return date ? date.split('-').reverse().join('/') : 'Chưa có ngày'
}
export function initials(name: string) {
  return name
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((s) => s[0])
    .join('')
    .toUpperCase()
}

export function exportMeeting(meeting: Meeting, format: 'txt' | 'md' | 'json') {
  if (format === 'json')
    return JSON.stringify(
      { schema_version: 'preview-1', demo: true, meeting },
      null,
      2,
    )
  const md = format === 'md'
  const heading = (s: string) => `${md ? '## ' : ''}${s}`
  return [
    `${md ? '# ' : ''}${meeting.title}`,
    formatDate(meeting.date),
    '',
    heading('Transcript'),
    ...meeting.segments.map(
      (s) =>
        `[${formatTime(s.start)}] ${meeting.speakers.find((p) => p.id === s.speakerId)?.name || 'Chưa xác định'}\n${s.text}\n`,
    ),
    heading('Tổng quan'),
    meeting.overview,
    '',
    heading('Ý chính'),
    ...meeting.points.map((p) => `- ${p.text}`),
    '',
    heading('Quyết định'),
    ...meeting.decisions.map((p) => `- ${p.text}`),
    '',
    heading('Công việc'),
    ...meeting.tasks.map(
      (t) =>
        `- [${t.done ? 'x' : ' '}] ${t.text} · ${t.assignee || 'Chưa giao'} · ${t.dueDate ? formatDate(t.dueDate) : 'Chưa có hạn'}`,
    ),
  ].join('\n')
}
