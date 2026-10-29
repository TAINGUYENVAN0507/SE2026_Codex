// Stack riêng cho E2E; không tái sử dụng API hoặc database phát triển.
import { spawn, spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'

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
const env = {
  ...process.env,
  DATABASE_URL: database,
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
function cleanup(code = 0) {
  if (stopping) return
  stopping = true
  for (const child of children) {
    if (!child.pid) continue
    try {
      if (process.platform === 'win32')
        spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], {
          stdio: 'ignore',
        })
      else process.kill(-child.pid, 'SIGTERM')
    } catch {
      /* Tiến trình có thể đã dừng. */
    }
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
    ['run', '--no-sync', 'python', '-m', 'app.worker.runner'],
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
