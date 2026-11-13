import { performance } from 'node:perf_hooks'
import { writeFileSync, mkdirSync } from 'node:fs'
import { platform, cpus } from 'node:os'
import { resolve } from 'node:path'

const runId = process.env.VT019_RUN_ID
if (runId && !/^[a-z0-9-]+$/.test(runId))
  throw new Error('Run ID evidence không hợp lệ')
const evidenceDir = resolve('vt019/evidence', runId ?? '.')
import { createAutosave } from '../src/features/meetings/autosave.ts'

// Harness controller + adapter giả lập; KHÔNG đại diện HTTP/DB production.
const concurrency = 120
const waves = 10
const samples: number[] = []
let maximum = 0
let errors = 0
for (let wave = 0; wave < waves; wave += 1) {
  let active = 0
  let release!: () => void
  const barrier = new Promise<void>((resolve) => {
    release = resolve
  })
  const sessions = Array.from({ length: concurrency }, () =>
    createAutosave({ text: 'Fixture gốc', version: 1 }, async (patch) => {
      active += 1
      maximum = Math.max(maximum, active)
      await barrier
      await new Promise((resolve) => setTimeout(resolve, 20))
      active -= 1
      return { text: patch.text, version: patch.version + 1 }
    }),
  )
  const work = sessions.map(async (session, index) => {
    session.edit(
      `Bản nháp tổng hợp ${wave}-${index} ` + 'nội dung '.repeat(125),
    )
    const start = performance.now()
    if (!(await session.flush())) errors += 1
    samples.push(performance.now() - start)
  })
  if (active !== concurrency) throw new Error('Chưa tạo đủ concurrency')
  release()
  await Promise.all(work)
}
samples.sort((a, b) => a - b)
const quantile = (q: number) => samples[Math.ceil(samples.length * q) - 1]
const result = {
  kind: 'controller with synthetic 20ms adapter; no HTTP/DB/browser',
  node: process.version,
  platform: platform(),
  cpu: cpus()[0]?.model,
  concurrency,
  maximum_in_flight: maximum,
  waves,
  samples: samples.length,
  errors,
  p50_ms: quantile(0.5),
  p95_ms: quantile(0.95),
  max_ms: samples.at(-1),
  target_p95_ms: 3500,
  passes_harness_target: quantile(0.95) <= 3500,
  excludes:
    '500ms debounce, HTTP, TLS, auth, database, multi-process contention',
}
mkdirSync(evidenceDir, { recursive: true })
writeFileSync(
  resolve(evidenceDir, 'load.json'),
  JSON.stringify(result, null, 2) + '\n',
)
writeFileSync(
  resolve(evidenceDir, 'load-samples.json'),
  JSON.stringify(samples) + '\n',
)
process.stdout.write(JSON.stringify(result, null, 2) + '\n')
