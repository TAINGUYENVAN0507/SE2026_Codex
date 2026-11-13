import {
  execFileSync,
  spawn,
  spawnSync,
  type ChildProcess,
} from 'node:child_process'
import { createWriteStream } from 'node:fs'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect } from '../fixtures.js'
import { uploadMeeting } from '../meeting.js'

const root = fileURLToPath(new URL('../../../', import.meta.url))
const destination = path.join(root, 'docs/evidence/vt-018/ui')
const backend = path.join(root, 'backend')

test('VT-018: capture queued, running, succeeded and a failed job retry without duplicate segments', async ({
  page,
}, testInfo) => {
  await mkdir(destination, { recursive: true })
  let worker: ChildProcess | undefined
  function stopWorker() {
    if (!worker?.pid) return
    if (process.platform === 'win32')
      spawnSync('taskkill', ['/PID', String(worker.pid), '/T', '/F'], {
        stdio: 'ignore',
      })
    else process.kill(-worker.pid, 'SIGTERM')
    worker = undefined
  }
  function startWorker(scenario: string) {
    const log = createWriteStream(testInfo.outputPath(`worker-${scenario}.log`))
    worker = spawn(
      process.env.UV || 'uv',
      ['run', '--no-sync', 'python', '-m', 'app.worker.runner'],
      {
        cwd: backend,
        detached: process.platform !== 'win32',
        env: {
          ...process.env,
          DATABASE_URL: process.env.E2E_DATABASE_URL,
          DEBUG: 'false',
          ENVIRONMENT: 'development',
          PIPELINE_BACKEND: 'fake',
          FAKE_SCENARIO: scenario,
          FAKE_STAGE_SLEEP_SEC: '2',
          LLM_PROVIDER: 'disabled',
          PYTHONUTF8: '1',
        },
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    )
    worker.stdout?.pipe(log)
    worker.stderr?.pipe(log)
    worker.on('exit', () => log.end())
    worker.on('error', (error) => log.end(error.name))
  }
  async function job(id: string) {
    const response = await page.request.get(`/api/v1/jobs/${id}`)
    expect(response.status()).toBe(200)
    const data = await response.json()
    return Object.fromEntries(
      [
        'id',
        'status',
        'stage',
        'progress',
        'attempt',
        'max_attempts',
        'created_at',
        'started_at',
        'finished_at',
      ].map((key) => [key, data[key]]),
    )
  }
  async function segments(meetingId: string) {
    const response = await page.request.get(
      `/api/v1/meetings/${meetingId}/transcript`,
    )
    expect(response.status()).toBe(200)
    const data = await response.json()
    return data.segments as { id: string }[]
  }
  const progress = page.getByRole('region', { name: 'Tiến độ xử lý cuộc họp' })
  async function photograph(name: string) {
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({
      path: path.join(destination, name),
      fullPage: true,
      animations: 'disabled',
    })
  }
  const evidence: Record<string, unknown> = {
    source_commit: execFileSync('git', ['rev-parse', 'HEAD'], {
      cwd: root,
      encoding: 'utf8',
    }).trim(),
    synthetic_only: true,
    pipeline: 'fake',
    captured_at_utc: new Date().toISOString(),
  }
  try {
    const first = await uploadMeeting(page, 'VT-018 · Kiểm chứng tiến độ')
    await page.goto(`/meetings/${first.meeting.id}/processing`)
    await expect(progress.getByRole('status')).toHaveText('Đang chờ xử lý')
    const queued = await job(first.job.id)
    expect(queued.status).toBe('queued')
    expect(queued.progress).toBe(0)
    evidence.queued = queued
    await photograph('01-queued.png')

    startWorker('slow')
    await expect(progress.getByRole('status')).toHaveText('Đang xử lý')
    await expect
      .poll(async () =>
        Number(
          await progress.getByRole('progressbar').getAttribute('aria-valuenow'),
        ),
      )
      .toBeGreaterThanOrEqual(40)
    const running = await job(first.job.id)
    expect(running.status).toBe('running')
    expect(running.progress).toBeGreaterThan(0)
    expect(running.progress).toBeLessThan(1)
    evidence.running = running
    await photograph('02-running.png')

    await expect(progress.getByRole('status')).toHaveText('Hoàn tất xử lý', {
      timeout: 90_000,
    })
    await expect(progress.locator('time[datetime]')).toHaveCount(2)
    const succeeded = await job(first.job.id)
    expect(succeeded.status).toBe('succeeded')
    expect(succeeded.started_at).toBeTruthy()
    expect(succeeded.finished_at).toBeTruthy()
    evidence.succeeded = succeeded
    await photograph('03-succeeded.png')
    stopWorker()

    startWorker('summary_fail')
    const second = await uploadMeeting(page, 'VT-018 · Chạy lại tóm tắt')
    await expect(progress.getByRole('status')).toHaveText('Xử lý thất bại', {
      timeout: 90_000,
    })
    const failed = await job(second.job.id)
    expect(failed.status).toBe('failed')
    stopWorker()
    const before = await segments(second.meeting.id)
    expect(before.length).toBeGreaterThan(0)
    const created = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        response.url().endsWith(`/meetings/${second.meeting.id}/jobs`),
    )
    await page
      .getByRole('button', { name: 'Tạo lại tóm tắt', exact: true })
      .click()
    const response = await created
    expect(response.status()).toBe(202)
    const retried = await response.json()
    expect(retried.id).not.toBe(second.job.id)
    await page.goto(`/meetings/${second.meeting.id}/processing`)
    await expect(progress.getByRole('status')).toHaveText('Đang chờ xử lý')
    // Retry từ summarize giữ năm bước trước; API khởi tạo progress = 5/6.
    expect(retried.progress).toBeCloseTo(5 / 6)
    expect(retried.attempt).toBe(1)
    expect(retried.started_at).toBeNull()
    expect(retried.finished_at).toBeNull()
    await expect(progress.getByRole('progressbar')).toHaveAttribute(
      'aria-valuenow',
      String(retried.progress * 100),
    )
    evidence.retry = { previous: failed, current: await job(retried.id) }
    await photograph('04-retry-reset.png')

    startWorker('slow')
    await expect(progress.getByRole('status')).toHaveText('Hoàn tất xử lý', {
      timeout: 90_000,
    })
    const after = await segments(second.meeting.id)
    expect(after.map((segment) => segment.id)).toEqual(
      before.map((segment) => segment.id),
    )
    expect(new Set(after.map((segment) => segment.id)).size).toBe(after.length)
    await page.goto(`/meetings/${second.meeting.id}`)
    const transcript = page.getByRole('region', {
      name: 'Transcript',
      exact: true,
    })
    await expect(
      transcript.getByRole('button', { name: /^Sửa đoạn / }),
    ).toHaveCount(after.length)
    evidence.segment_check = {
      before_ids: before.map((segment) => segment.id),
      after_ids: after.map((segment) => segment.id),
      rendered_count: after.length,
    }
    // Chỉ giữ field vận hành; không ghi cookie, mật khẩu hay nội dung transcript.
    await writeFile(
      path.join(destination, 'capture.json'),
      JSON.stringify(evidence, null, 2) + '\n',
      'utf8',
    )
  } finally {
    stopWorker()
  }
})
