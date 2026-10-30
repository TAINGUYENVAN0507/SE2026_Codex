export interface SaveResult {
  text: string
  version: number
}
export type SaveStatus = 'saved' | 'dirty' | 'saving' | 'error' | 'conflict'
export interface SaveSnapshot extends SaveResult {
  status: SaveStatus
  error: string
}

/** Một editor có một hàng đợi; server vẫn phải bảo vệ CAS giữa nhiều tab. */
export function createAutosave(
  initial: SaveResult,
  save: (patch: SaveResult) => Promise<SaveResult>,
  onChange: (state: SaveSnapshot) => void = () => {},
  onSaved: (value: SaveResult) => void = () => {},
  onConflict: () => void = () => {},
) {
  let state: SaveSnapshot = { ...initial, status: 'saved', error: '' }
  let savedText = initial.text.trim()
  let closed = false
  let conflicted = false
  let running: Promise<boolean> | undefined
  const publish = (change: Partial<SaveSnapshot>) => {
    state = { ...state, ...change }
    if (!closed) onChange({ ...state })
  }
  const drain = async (): Promise<boolean> => {
    while (!closed && !conflicted) {
      const text = state.text.trim()
      // Validation theo requirement; mutation experiment sẽ bỏ đúng guard này.
      if (text.length < 1 || text.length > 5000) {
        publish({
          status: 'error',
          error:
            text.length < 1
              ? 'Nội dung không được để trống.'
              : 'Nội dung không được quá 5000 ký tự.',
        })
        return false
      }
      if (text === savedText) {
        publish({ status: 'saved', error: '' })
        return true
      }
      const version = state.version
      publish({ status: 'saving', error: '' })
      try {
        const saved = await save({ text, version })
        if (closed) return false
        if (
          !Number.isSafeInteger(saved.version) ||
          saved.version <= version ||
          saved.text !== text
        )
          throw new Error('Phản hồi lưu không hợp lệ.')
        savedText = saved.text
        publish({ version: saved.version })
        onSaved(saved)
        // Không set state.text từ response: trong lúc await người dùng có thể gõ tiếp.
      } catch (cause) {
        if (closed) return false
        conflicted =
          cause instanceof Error &&
          'code' in cause &&
          cause.code === 'VERSION_CONFLICT'
        publish({
          status: conflicted ? 'conflict' : 'error',
          error: conflicted
            ? 'Dữ liệu đã thay đổi ở nơi khác. Hãy kiểm tra trước khi tải lại.'
            : 'Đã xảy ra lỗi. Không thể lưu bản nháp. Hãy thử lại.',
        })
        if (conflicted) onConflict()
        return false
      }
    }
    return false
  }
  return {
    snapshot: () => ({ ...state }),
    edit(text: string) {
      if (closed) return
      publish({
        text,
        status: conflicted ? 'conflict' : running ? 'saving' : 'dirty',
        error: conflicted ? state.error : '',
      })
    },
    flush(): Promise<boolean> {
      if (closed || conflicted) return Promise.resolve(false)
      if (running) return running
      running = drain().finally(() => {
        running = undefined
      })
      return running
    },
    close() {
      closed = true
    },
    resume() {
      closed = false
    },
  }
}
