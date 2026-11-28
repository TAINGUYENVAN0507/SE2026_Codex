import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  realpathSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import {
  cleanupAfterStack,
  configureStorage,
  createStorage,
} from '../../e2e/storage.mjs'

const owned: ReturnType<typeof createStorage>[] = []
const foreign: string[] = []
beforeEach(() => {
  vi.stubEnv('E2E_STORAGE_DIR', '')
  vi.stubEnv('STORAGE_DIR', '')
  vi.stubEnv('E2E_STORAGE_OWNER', '')
})
afterEach(() => {
  for (const storage of owned.splice(0)) storage.cleanup()
  for (const folder of foreign.splice(0)) {
    const checked = realpathSync(folder)
    if (
      path.dirname(checked) !== realpathSync(tmpdir()) ||
      !path.basename(checked).startsWith('se-e2e-foreign-')
    )
      throw new Error('Sai thư mục tạm của test.')
    rmSync(checked, { recursive: true })
  }
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
})
it('launcher và worker dùng cùng đường dẫn; chỉ dọn thư mục do stack tạo', () => {
  const configured = configureStorage()
  expect(configureStorage()).toBe(configured)
  expect(process.env.STORAGE_DIR).toBe(configured)
  expect(existsSync(configured)).toBe(false)
  const storage = createStorage()
  owned.push(storage)
  expect(storage.directory).toBe(configured)
  expect(path.dirname(realpathSync(configured))).toBe(realpathSync(tmpdir()))
  mkdirSync(path.join(configured, 'audio'))
  writeFileSync(path.join(configured, 'audio', 'synthetic.txt'), 'synthetic')
  storage.cleanup()
  expect(existsSync(configured)).toBe(false)
  storage.cleanup()
})
it('không dùng lại hay xóa storage đang có của một stack khác', () => {
  const storage = createStorage()
  owned.push(storage)
  writeFileSync(path.join(storage.directory, 'sentinel'), 'keep')
  expect(() => createStorage()).toThrow()
  expect(readFileSync(path.join(storage.directory, 'sentinel'), 'utf8')).toBe(
    'keep',
  )
})
it('từ chối đường dẫn bên ngoài namespace tạm mà không chạm file sẵn có', () => {
  const folder = mkdtempSync(path.join(tmpdir(), 'se-e2e-foreign-'))
  foreign.push(folder)
  writeFileSync(path.join(folder, 'sentinel'), 'keep')
  vi.stubEnv('E2E_STORAGE_DIR', folder)
  expect(() => createStorage()).toThrow('E2E_STORAGE_DIR')
  expect(readFileSync(path.join(folder, 'sentinel'), 'utf8')).toBe('keep')
})
it('dấu sở hữu đổi thì không xóa dữ liệu', () => {
  const storage = createStorage()
  owned.push(storage)
  const marker = path.join(storage.directory, '.se-e2e-owner')
  const original = readFileSync(marker, 'utf8')
  writeFileSync(marker, 'changed')
  try {
    expect(() => storage.cleanup()).toThrow('sở hữu')
    expect(existsSync(storage.directory)).toBe(true)
  } finally {
    writeFileSync(marker, original)
  }
})

it('reporter dọn storage có token đúng sau khi tiến trình stack đã chết', () => {
  const storage = createStorage()
  owned.push(storage)
  vi.spyOn(process, 'kill').mockImplementation(() => {
    throw Object.assign(new Error('ended'), { code: 'ESRCH' })
  })
  cleanupAfterStack()
  expect(existsSync(storage.directory)).toBe(false)
})
it('reporter không dọn sớm khi tiến trình stack còn chạy', () => {
  const storage = createStorage()
  owned.push(storage)
  vi.spyOn(process, 'kill').mockReturnValue(true)
  cleanupAfterStack()
  expect(existsSync(storage.directory)).toBe(true)
})
