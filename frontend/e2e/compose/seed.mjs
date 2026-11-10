// Mật khẩu tổng hợp chỉ truyền qua stdin, không có trên command line/log.
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
const root = fileURLToPath(new URL('../../..', import.meta.url))
const project = process.env.COMPOSE_PROJECT_NAME || 'se-web-e2e'
if (!/^se-[a-z0-9-]*e2e[a-z0-9-]*$/.test(project))
  throw new Error('Compose project phải là stack se-...e2e riêng.')
const password = process.env.COMPOSE_E2E_PASSWORD
if (!password)
  throw new Error('Thiếu COMPOSE_E2E_PASSWORD cho tài khoản tổng hợp.')
const args = [
  'compose',
  '-p',
  project,
  '-f',
  'docker-compose.yml',
  '-f',
  'frontend/e2e/compose/override.yml',
  'exec',
  '-T',
  'api',
  'python',
  '-m',
  'app.scripts.create_user',
  '--email',
  process.env.COMPOSE_E2E_EMAIL || 'compose-e2e@example.local',
  '--name',
  'Compose E2E',
]
const result = spawnSync('docker', args, {
  cwd: root,
  input: password + '\n',
  encoding: 'utf8',
})
if (result.status !== 0)
  throw new Error(
    'Không tạo được user tổng hợp trong Compose; kiểm log API và database test.',
  )
console.log('Đã tạo user tổng hợp trong Compose E2E.')
