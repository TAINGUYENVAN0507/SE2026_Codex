// FE-17: chỉ nhận và dọn thư mục tạm riêng, không dùng STORAGE_DIR của máy phát triển.
import { randomUUID } from 'node:crypto'
import { tmpdir } from 'node:os'
import path from 'node:path'
import {
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  realpathSync,
  rmSync,
  rmdirSync,
  writeFileSync,
} from 'node:fs'

const prefix = 'se-e2e-storage-'
const marker = '.se-e2e-owner'
function checkedDirectory(value) {
  const root = realpathSync(tmpdir())
  const resolved = path.resolve(value)
  if (
    realpathSync(path.dirname(resolved)) !== root ||
    !path.basename(resolved).startsWith(prefix)
  )
    throw new Error(
      'E2E_STORAGE_DIR phải là thư mục riêng ngay trong thư mục tạm hệ thống.',
    )
  return path.join(root, path.basename(resolved))
}
export function configureStorage() {
  const directory = checkedDirectory(
    process.env.E2E_STORAGE_DIR || path.join(tmpdir(), prefix + randomUUID()),
  )
  if (!process.env.E2E_STORAGE_OWNER)
    process.env.E2E_STORAGE_OWNER = randomUUID()
  process.env.E2E_STORAGE_DIR = directory
  process.env.STORAGE_DIR = directory
  return directory
}
export function createStorage() {
  const directory = configureStorage()
  // mkdir không recursive: tuyệt đối không nhận lại thư mục đang có sẵn.
  mkdirSync(directory)
  const token = process.env.E2E_STORAGE_OWNER
  try {
    writeFileSync(
      path.join(directory, marker),
      JSON.stringify({ token, pid: process.pid }),
      {
        flag: 'wx',
        mode: 0o600,
      },
    )
  } catch (error) {
    rmdirSync(directory)
    throw error
  }
  return {
    directory,
    cleanup() {
      cleanupStorage(directory, token)
    },
  }
}

function ownerOf(directory) {
  try {
    const owner = JSON.parse(readFileSync(path.join(directory, marker), 'utf8'))
    if (
      typeof owner.token !== 'string' ||
      !Number.isSafeInteger(owner.pid) ||
      owner.pid <= 0
    )
      throw new Error()
    return owner
  } catch {
    throw new Error('Không dọn storage E2E vì dấu sở hữu không hợp lệ.')
  }
}
export function cleanupStorage(directory, token) {
  if (!existsSync(directory)) return
  // Kiểm đường dẫn thực và token của chính lượt chạy trước khi xóa đệ quy.
  if (
    checkedDirectory(directory) !== directory ||
    lstatSync(directory).isSymbolicLink() ||
    realpathSync(directory) !== directory ||
    ownerOf(directory).token !== token
  )
    throw new Error(
      'Không dọn storage E2E vì đường dẫn hoặc dấu sở hữu đã thay đổi.',
    )
  rmSync(directory, {
    recursive: true,
    force: false,
    maxRetries: 10,
    retryDelay: 100,
  })
}
export function cleanupAfterStack() {
  const directory = process.env.E2E_STORAGE_DIR
  const token = process.env.E2E_STORAGE_OWNER
  if (!directory || !token || !existsSync(directory)) return
  const owner = ownerOf(checkedDirectory(directory))
  if (owner.token !== token)
    throw new Error('Không nhận storage của lượt E2E khác.')
  try {
    process.kill(owner.pid, 0)
    return
  } catch (error) {
    if (error.code !== 'ESRCH') throw error
  }
  // Reporter onExit chạy sau teardown. Cần fallback vì Windows dừng cứng cây tiến trình.
  cleanupStorage(directory, token)
}
