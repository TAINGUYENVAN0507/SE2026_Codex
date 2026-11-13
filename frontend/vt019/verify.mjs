import { spawnSync } from 'node:child_process'
import {
  mkdirSync,
  writeFileSync,
  readFileSync,
  existsSync,
  copyFileSync,
  symlinkSync,
  unlinkSync,
} from 'node:fs'
import { resolve, dirname, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

// Chỉ chạy trong clone riêng Lab03; không fetch/push/merge.
const frontend = fileURLToPath(new URL('../', import.meta.url))
const repo = dirname(frontend)
const labRoot = resolve(repo, '..')
if (labRoot.toLowerCase() !== 'd:\\project\\se2026\\lab03')
  throw new Error('Bài này chỉ được chạy trong D:/Project/SE2026/Lab03')
const runId = process.argv[2]
if (!/^[a-z0-9-]+$/.test(runId ?? '')) throw new Error('Cần run ID mới')
const evidence = resolve(frontend, 'vt019/evidence', runId)
if (existsSync(evidence))
  throw new Error('Evidence đã tồn tại; dùng run ID mới')
mkdirSync(evidence, { recursive: true })
const started = new Date().toISOString()
const env = {
  ...process.env,
  VT019_RUN_ID: runId,
  NO_COLOR: '1',
  FORCE_COLOR: '0',
}
const results = []
function execute(label, command, args, cwd = frontend, expected = 0, needle) {
  const run = spawnSync(command, args, {
    cwd,
    env,
    encoding: 'utf8',
    maxBuffer: 16 * 1024 * 1024,
  })
  if (run.error) throw run.error
  const output = (run.stdout ?? '') + (run.stderr ?? '')
  writeFileSync(
    resolve(evidence, `${label}.log`),
    `$ ${command} ${args.join(' ')}\n${output}\nEXIT=${run.status}\n`,
  )
  const passed = run.status === expected && (!needle || needle.test(output))
  results.push({ label, exit: run.status, expected_exit: expected, passed })
  process.stdout.write(
    `${label}: exit=${run.status}, expected=${expected}, ${passed ? 'OK' : 'FAIL'}\n`,
  )
  if (!passed) throw new Error(`Kiểm tra ${label} thất bại; xem log riêng`)
}
const node = (label, tool, ...args) =>
  execute(label, process.execPath, [tool, ...args])
function git(...args) {
  const run = spawnSync('git', args, { cwd: repo, encoding: 'utf8' })
  if (run.error || run.status !== 0)
    throw new Error(run.stderr || 'Git thất bại')
  return run.stdout.trim()
}
const baseline = '53f753b3afe6c1a2d54ff1e38a72dee30c6074d2'
const mutant = '8062f6011d606bd063464533dbecefbf57ee3c71'
const head = git('rev-parse', 'HEAD')
function replay(label, revision, testFile, oracle) {
  const parent = resolve(labRoot, 'tmp', 'verification-worktrees', runId)
  const target = resolve(parent, label)
  if (
    !target.startsWith(labRoot + sep) ||
    !target.startsWith(parent + sep) ||
    existsSync(target)
  )
    throw new Error('Worktree phải mới và nằm bên trong Lab03/tmp')
  mkdirSync(parent, { recursive: true })
  git('worktree', 'add', '--detach', target, revision)
  const workingFrontend = resolve(target, 'frontend')
  const modules = resolve(workingFrontend, 'node_modules')
  let linked = false
  try {
    if (label === 'baseline-replay')
      copyFileSync(
        resolve(frontend, testFile),
        resolve(workingFrontend, testFile),
      )
    symlinkSync(resolve(frontend, 'node_modules'), modules, 'junction')
    linked = true
    execute(
      label,
      process.execPath,
      [resolve(frontend, 'node_modules/vitest/vitest.mjs'), 'run', testFile],
      workingFrontend,
      1,
      oracle,
    )
  } finally {
    // Tháo junction trước khi dọn checkout; không xóa dependency của bài.
    if (linked) unlinkSync(modules)
    git('worktree', 'remove', '--force', target)
  }
}
try {
  node('lint', 'node_modules/eslint/bin/eslint.js', '.')
  node('oxlint', 'node_modules/oxlint/bin/oxlint', '.')
  node('format', 'node_modules/prettier/bin/prettier.cjs', '--check', '.')
  node(
    'typecheck',
    'node_modules/typescript/bin/tsc',
    '-b',
    '--pretty',
    'false',
  )
  node(
    'green-full',
    'node_modules/vitest/vitest.mjs',
    'run',
    '--coverage.enabled',
    '--coverage.provider=v8',
    '--coverage.include=src/features/meetings/autosave.ts',
    '--coverage.include=src/features/meetings/AutosaveEditor.tsx',
    '--coverage.reporter=json-summary',
    '--coverage.reporter=text',
    `--coverage.reportsDirectory=${relative(frontend, resolve(evidence, 'coverage'))}`,
  )
  for (const seed of [19, 23, 29])
    node(
      `flaky-${seed}`,
      'node_modules/vitest/vitest.mjs',
      'run',
      'src/features/meetings/autosave.test.ts',
      'src/features/meetings/autosaveApi.test.ts',
      'src/features/meetings/AutosaveEditor.test.tsx',
      'src/features/meetings/TranscriptAutosave.test.tsx',
      '--sequence.shuffle',
      `--sequence.seed=${seed}`,
    )
  node('build', 'node_modules/vite/bin/vite.js', 'build')
  node(
    'e2e',
    'node_modules/@playwright/test/cli.js',
    'test',
    '--config',
    'vt019/playwright.config.ts',
  )
  node('load', 'vt019/load.mts')
  const load = JSON.parse(readFileSync(resolve(evidence, 'load.json'), 'utf8'))
  if (
    load.maximum_in_flight !== 120 ||
    load.samples !== 1200 ||
    load.errors !== 0 ||
    !load.passes_harness_target
  )
    throw new Error('Harness không đạt điều kiện đã khai báo')
  replay(
    'baseline-replay',
    baseline,
    'src/features/meetings/TranscriptAutosave.test.tsx',
    /Number of calls: 0/,
  )
  replay(
    'mutation-replay',
    mutant,
    'src/features/meetings/autosave.test.ts',
    /3 failed\s*\|\s*12 passed/,
  )
  execute(
    'mutation-not-ancestor',
    'git',
    ['merge-base', '--is-ancestor', mutant, 'HEAD'],
    repo,
    1,
  )
  if (
    !readFileSync(
      resolve(frontend, 'src/features/meetings/autosave.ts'),
      'utf8',
    ).includes('text.length < 1 || text.length > 5000')
  )
    throw new Error('Validation chưa được khôi phục')
} finally {
  writeFileSync(
    resolve(evidence, 'verification.json'),
    JSON.stringify(
      {
        run_id: runId,
        started_utc: started,
        finished_utc: new Date().toISOString(),
        node: process.version,
        platform: process.platform,
        head,
        baseline,
        mutant,
        note: 'Replay hiện tại; không thay thế bằng chứng test-first lịch sử. API/browser/tải dùng fixture, chưa chứng minh backend thật.',
        checks: results,
      },
      null,
      2,
    ) + '\n',
  )
}
