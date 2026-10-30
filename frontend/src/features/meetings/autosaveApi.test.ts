import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it } from 'vitest'
import { patchSegment } from '../../api/client'
import { createAutosave } from './autosave'

const server = setupServer()
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

it('TC14 integration client HTTP + CAS mock: hai tab cùng version', async () => {
  let version = 1
  let content = 'Gốc'
  let count = 0
  server.use(
    http.patch(
      '*/api/v1/meetings/:meetingId/segments/:segmentId',
      async ({ request }) => {
        const patch = (await request.json()) as {
          text: string
          version: number
        }
        count += 1
        if (patch.version !== version)
          return HttpResponse.json(
            { error: { code: 'VERSION_CONFLICT', message: 'Xung đột' } },
            { status: 409 },
          )
        content = patch.text
        version += 1
        return HttpResponse.json({ text: content, version })
      },
    ),
  )
  const save = (patch: { text: string; version: number }) =>
    patchSegment('m', 's', patch)
  const a = createAutosave({ text: content, version }, save)
  const b = createAutosave({ text: content, version }, save)
  a.edit('Tab A')
  b.edit('Tab B')
  const result = await Promise.all([a.flush(), b.flush()])
  expect(result.filter(Boolean)).toHaveLength(1)
  expect([a.snapshot().status, b.snapshot().status].sort()).toEqual([
    'conflict',
    'saved',
  ])
  const loser = a.snapshot().status === 'conflict' ? a : b
  const draft = loser.snapshot().text
  expect(await loser.flush()).toBe(false)
  expect(loser.snapshot().text).toBe(draft)
  expect(count).toBe(2)
  expect(version).toBe(2)
})

it('TC15 HTTP 500 giữ draft và cho retry chủ động', async () => {
  server.use(
    http.patch('*/api/v1/meetings/:meetingId/segments/:segmentId', () =>
      HttpResponse.json(
        { error: { code: 'UNKNOWN_ERROR', message: 'Lỗi giả lập' } },
        { status: 500 },
      ),
    ),
  )
  const session = createAutosave({ text: 'Gốc', version: 1 }, (patch) =>
    patchSegment('m', 's', patch),
  )
  session.edit('Draft giữ lại')
  expect(await session.flush()).toBe(false)
  expect(session.snapshot()).toMatchObject({
    text: 'Draft giữ lại',
    status: 'error',
    version: 1,
  })
  server.use(
    http.patch('*/api/v1/meetings/:meetingId/segments/:segmentId', () =>
      HttpResponse.json({ text: 'Draft giữ lại', version: 2 }),
    ),
  )
  expect(await session.flush()).toBe(true)
})
