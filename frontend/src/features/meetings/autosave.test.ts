import { describe, expect, it, vi } from 'vitest'
import { createAutosave, type SaveResult } from './autosave'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (cause: Error) => void
  const promise = new Promise<T>((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}

describe('VT-019 contract, oracle từ AC trước implementation', () => {
  it('TC02 A chậm không ghi đè C mới; B được gộp, version tăng', async () => {
    const a = deferred<SaveResult>()
    const c = deferred<SaveResult>()
    const save = vi
      .fn()
      .mockReturnValueOnce(a.promise)
      .mockReturnValueOnce(c.promise)
    const session = createAutosave({ text: 'Gốc', version: 1 }, save)
    session.edit('A')
    const pending = session.flush()
    session.edit('B')
    session.edit('C')
    void session.flush()
    expect(save).toHaveBeenCalledTimes(1)
    a.resolve({ text: 'A', version: 2 })
    await a.promise
    await Promise.resolve()
    expect(session.snapshot().text).toBe('C')
    expect(save.mock.calls).toEqual([
      [{ text: 'A', version: 1 }],
      [{ text: 'C', version: 2 }],
    ])
    c.resolve({ text: 'C', version: 3 })
    expect(await pending).toBe(true)
    expect(session.snapshot()).toMatchObject({
      text: 'C',
      version: 3,
      status: 'saved',
    })
  })

  it('TC03 hai editor cùng version: một thành công, một conflict, giữ draft', async () => {
    let version = 1
    let stored = 'Gốc'
    const save = async (patch: SaveResult) => {
      await Promise.resolve()
      if (patch.version !== version)
        throw Object.assign(new Error('Xung đột'), { code: 'VERSION_CONFLICT' })
      version += 1
      stored = patch.text
      return { text: stored, version }
    }
    const a = createAutosave({ text: stored, version }, save)
    const b = createAutosave({ text: stored, version }, save)
    a.edit('Tab A')
    b.edit('Tab B')
    expect(await Promise.all([a.flush(), b.flush()])).toEqual([true, false])
    expect(stored).toBe('Tab A')
    expect(b.snapshot()).toMatchObject({
      text: 'Tab B',
      status: 'conflict',
      version: 1,
    })
    b.edit('Chữ sau conflict')
    expect(await b.flush()).toBe(false)
    expect(stored).toBe('Tab A')
  })

  it.each(['', '   ', 'a'.repeat(5001)])(
    'TC04 input không hợp lệ không gửi PATCH (%#)',
    async (text) => {
      const save = vi.fn(async (patch: SaveResult) => ({
        ...patch,
        version: 2,
      }))
      const session = createAutosave({ text: 'Gốc', version: 1 }, save)
      session.edit(text)
      expect(await session.flush()).toBe(false)
      expect(save).not.toHaveBeenCalled()
      expect(session.snapshot()).toMatchObject({ text, status: 'error' })
    },
  )

  it.each(['a', 'a'.repeat(5000)])(
    'TC05 boundary hợp lệ (%#)',
    async (text) => {
      const save = vi.fn(async (patch: SaveResult) => ({
        ...patch,
        version: patch.version + 1,
      }))
      const session = createAutosave({ text: 'Gốc', version: 1 }, save)
      session.edit(text)
      expect(await session.flush()).toBe(true)
      expect(save).toHaveBeenCalledWith({ text, version: 1 })
    },
  )

  it('TC06 lỗi mạng giữ draft; retry gửi bản mới nhất', async () => {
    const save = vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ text: 'Mới nhất', version: 2 })
    const session = createAutosave({ text: 'Gốc', version: 1 }, save)
    session.edit('Chưa lưu')
    expect(await session.flush()).toBe(false)
    expect(session.snapshot()).toMatchObject({
      text: 'Chưa lưu',
      status: 'error',
    })
    session.edit('Mới nhất')
    expect(await session.flush()).toBe(true)
    expect(save.mock.calls[1]).toEqual([{ text: 'Mới nhất', version: 1 }])
  })

  it.each([0, 1, NaN, 1.5])(
    'TC07 response version không tiến bị từ chối (%#)',
    async (version) => {
      const session = createAutosave({ text: 'Gốc', version: 1 }, async () => ({
        text: 'Mới',
        version,
      }))
      session.edit('Mới')
      expect(await session.flush()).toBe(false)
      expect(session.snapshot()).toMatchObject({
        text: 'Mới',
        version: 1,
        status: 'error',
      })
    },
  )

  it('TC08 đóng editor khi đang lưu không gửi draft đang chờ', async () => {
    const a = deferred<SaveResult>()
    const save = vi.fn(() => a.promise)
    const session = createAutosave({ text: 'Gốc', version: 1 }, save)
    session.edit('A')
    const pending = session.flush()
    session.edit('B')
    session.close()
    a.resolve({ text: 'A', version: 2 })
    await pending
    expect(save).toHaveBeenCalledTimes(1)
    expect(await session.flush()).toBe(false)
  })

  it('TC09 no-op sau trim không tạo ghi dư', async () => {
    const save = vi.fn()
    const session = createAutosave({ text: 'Gốc', version: 1 }, save)
    session.edit('  Gốc  ')
    expect(await session.flush()).toBe(true)
    expect(save).not.toHaveBeenCalled()
    expect(session.snapshot().text).toBe('  Gốc  ')
  })

  it('TC10 response khác snapshot bị chặn; draft không bị thay', async () => {
    const session = createAutosave({ text: 'Gốc', version: 1 }, async () => ({
      text: 'Sai',
      version: 2,
    }))
    session.edit('Mới')
    expect(await session.flush()).toBe(false)
    expect(session.snapshot()).toMatchObject({
      text: 'Mới',
      version: 1,
      status: 'error',
    })
  })
})
