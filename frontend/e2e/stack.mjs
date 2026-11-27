// Stack riêng cho E2E; không tái sử dụng API hoặc database phát triển.
import { spawn, spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { createStorage } from './storage.mjs'

const frontend = fileURLToPath(new URL('..', import.meta.url))
const backend = path.resolve(frontend, '../backend')
const database = process.env.E2E_DATABASE_URL
if (!database || !new URL(database).pathname.toLowerCase().includes('e2e')) {
  throw new Error(
    'E2E_DATABASE_URL phải trỏ tới database riêng có tên chứa e2e.',
  )
}
if (!process.env.SEED_DEMO_PASSWORD)
  throw new Error('Thiếu SEED_DEMO_PASSWORD cho E2E.')
const storage = createStorage()
const env = {
  ...process.env,
  DATABASE_URL: database,
  STORAGE_DIR: storage.directory,
  E2E_STORAGE_DIR: storage.directory,
  DEBUG: 'false',
  ENVIRONMENT: 'development',
  PIPELINE_BACKEND: 'fake',
  FAKE_SCENARIO: process.env.FAKE_SCENARIO || 'slow',
  FAKE_STAGE_SLEEP_SEC: '2',
  VITE_API_MOCK: '0',
  VITE_API_PROXY_TARGET: 'http://127.0.0.1:18000',
  PYTHONUTF8: '1',
}
const uv = process.env.UV || 'uv'
const node = process.execPath
const children = new Set()
let stopping = false
async function stop(child) {
  if (!child.pid || child.exitCode !== null || child.signalCode !== null) return
  const exited = new Promise((resolve) =>
    child.once('exit', () => resolve(true)),
  )
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], {
      stdio: 'ignore',
    })
  } else {
    try {
      process.kill(-child.pid, 'SIGTERM')
    } catch {
      /* Có thể đã thoát. */
    }
  }
  if (await Promise.race([exited, delay(2000).then(() => false)])) return
  try {
    process.kill(-child.pid, 'SIGKILL')
  } catch {
    /* Có thể đã thoát. */
  }
  if (!(await Promise.race([exited, delay(1000).then(() => false)])))
    throw new Error(
      'Tiến trình E2E chưa dừng; giữ storage riêng để tránh xóa khi còn ghi.',
    )
}
async function cleanup(code = 0) {
  if (stopping) return
  stopping = true
  try {
    await Promise.all([...children].map(stop))
    storage.cleanup()
  } catch (error) {
    console.error(error)
    code = 1
  }
  process.exit(code)
}
process.on('SIGINT', () => cleanup())
process.on('SIGTERM', () => cleanup())
process.on('uncaughtException', (error) => {
  console.error(error)
  cleanup(1)
})
function start(command, args, cwd) {
  if (stopping) throw new Error('Stack E2E đang dừng.')
  const child = spawn(command, args, {
    cwd,
    env,
    stdio: 'inherit',
    detached: process.platform !== 'win32',
  })
  children.add(child)
  child.on('error', (error) => {
    console.error(error)
    cleanup(1)
  })
  return child
}
async function run(command, args, cwd) {
  const child = start(command, args, cwd)
  const code = await new Promise((resolve) => child.on('exit', resolve))
  children.delete(child)
  if (code !== 0) throw new Error(`Lệnh chuẩn bị stack thất bại (${code}).`)
}
async function healthy(url) {
  const deadline = Date.now() + 60_000
  while (Date.now() < deadline) {
    try {
      if ((await fetch(url, { signal: AbortSignal.timeout(2_000) })).ok) return
    } catch {
      /* Đợi dịch vụ sẵn sàng. */
    }
    await delay(250)
  }
  throw new Error(`Dịch vụ không sẵn sàng: ${url}`)
}
try {
  await run(uv, ['sync', '--locked'], backend)
  await run(uv, ['run', '--no-sync', 'alembic', 'upgrade', 'head'], backend)
  await run(
    uv,
    ['run', '--no-sync', 'python', '-m', 'app.scripts.seed'],
    backend,
  )
  await run(node, ['node_modules/typescript/bin/tsc', '-b'], frontend)
  await run(node, ['node_modules/vite/bin/vite.js', 'build'], frontend)
  for (const args of [
    [
      'run',
      '--no-sync',
      'uvicorn',
      'app.main:app',
      '--host',
      '127.0.0.1',
      '--port',
      '18000',
    ],
    // Ảnh bằng chứng cần giữ job queued trước khi bật worker do test quản lý.
    ...(process.env.E2E_MANUAL_WORKER === '1'
      ? []
      : [['run', '--no-sync', 'python', '-m', 'app.worker.runner']]),
  ]) {
    start(uv, args, backend).on('exit', (code) => {
      if (!stopping) cleanup(code || 1)
    })
  }
  await healthy('http://127.0.0.1:18000/api/v1/health')
  start(
    node,
    [
      'node_modules/vite/bin/vite.js',
      'preview',
      '--host',
      '127.0.0.1',
      '--port',
      '14173',
      '--strictPort',
    ],
    frontend,
  ).on('exit', (code) => {
    if (!stopping) cleanup(code || 1)
  })
} catch (error) {
  console.error(error)
  cleanup(1)
}
