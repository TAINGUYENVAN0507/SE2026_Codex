import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { fileURLToPath } from 'node:url'

const run = promisify(execFile)
export async function expireSyntheticAudio(meetingId: string) {
  const database = process.env.E2E_DATABASE_URL
  if (!database || !new URL(database).pathname.toLowerCase().includes('e2e'))
    throw new Error('Fixture chỉ chạy trên database E2E riêng.')
  const result = await run(
    process.env.UV || 'uv',
    [
      'run',
      '--no-sync',
      'python',
      fileURLToPath(new URL('./expire_audio.py', import.meta.url)),
      meetingId,
    ],
    {
      cwd: fileURLToPath(new URL('../../backend/', import.meta.url)),
      env: {
        ...process.env,
        DATABASE_URL: database,
        DEBUG: 'false',
        PYTHONUTF8: '1',
      },
      timeout: 30_000,
    },
  )
  return JSON.parse(result.stdout) as {
    audio_removed: boolean
    transcript_preserved: boolean
    segments: number
  }
}
