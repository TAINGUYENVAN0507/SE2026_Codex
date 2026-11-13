import { spawnSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Chỉ lưu output kiểm thử với fixture tổng hợp; không thu thập biến môi trường.
const [label, tool, ...args] = process.argv.slice(2)
const runId = process.env.VT019_RUN_ID
if (runId && !/^[a-z0-9-]+$/.test(runId))
  throw new Error('Run ID evidence không hợp lệ')
const evidenceDir = resolve('vt019/evidence', runId ?? '.')
if (!/^[a-z0-9-]+$/.test(label ?? ''))
  throw new Error('Nhãn evidence không hợp lệ')
const tools = {
  vitest: 'node_modules/vitest/vitest.mjs',
  prettier: 'node_modules/prettier/bin/prettier.cjs',
  tsc: 'node_modules/typescript/bin/tsc',
  eslint: 'node_modules/eslint/bin/eslint.js',
  oxlint: 'node_modules/oxlint/bin/oxlint',
  vite: 'node_modules/vite/bin/vite.js',
  playwright: 'node_modules/@playwright/test/cli.js',
}
if (!(tool in tools)) throw new Error('Công cụ không được phép')
const run = spawnSync(process.execPath, [tools[tool], ...args], {
  encoding: 'utf8',
  env: { ...process.env, NO_COLOR: '1', FORCE_COLOR: '0' },
})
if (run.error) throw run.error
mkdirSync(evidenceDir, { recursive: true })
writeFileSync(
  resolve(evidenceDir, `${label}.log`),
  `$ node ${tools[tool]} ${args.join(' ')}\n${run.stdout ?? ''}${run.stderr ?? ''}\nEXIT=${run.status}\n`,
)
process.stdout.write(run.stdout ?? '')
process.stderr.write(run.stderr ?? '')
process.exit(run.status ?? 1)
