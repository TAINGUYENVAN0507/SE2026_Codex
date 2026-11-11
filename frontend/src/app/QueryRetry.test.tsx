import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { act, cleanup, render } from '@testing-library/react'
import { useEffect } from 'react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, it, vi } from 'vitest'
import { AppProviders } from './AppProviders'
import { getConfig } from '../api/client'
import { ApiError } from '../api/errors'
import config from '../../../contracts/fixtures/api/config.json'

const server = setupServer()
const clients: QueryClient[] = []
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterAll(() => server.close())
afterEach(async () => {
  cleanup()
  for (const client of clients.splice(0)) {
    await client.cancelQueries()
    client.clear()
  }
  server.resetHandlers()
  vi.useRealTimers()
})

function setup() {
  vi.useFakeTimers()
  let captured!: QueryClient
  function CaptureClient() {
    const client = useQueryClient()
    useEffect(() => {
      captured = client
      clients.push(client)
    }, [client])
    return null
  }
  render(
    <AppProviders>
      <CaptureClient />
    </AppProviders>,
  )
  return captured
}
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}
function failure(status: number, retryAfter?: string) {
  return HttpResponse.json(
    {
      error: {
        code: status === 503 ? 'SERVICE_UNAVAILABLE' : 'HTTP_ERROR',
        message: 'RAW_CANARY',
      },
    },
    { status, headers: retryAfter ? { 'Retry-After': retryAfter } : undefined },
  )
}

it('AD-018: query đợi đúng Retry-After 3 giây rồi nhận dữ liệu 200', async () => {
  let requests = 0
  server.use(
    http.get('*/api/v1/config', () =>
      ++requests === 1 ? failure(503, '3') : HttpResponse.json(config),
    ),
  )
  const client = setup()
  let failedAt: number | undefined
  const unsubscribe = client.getQueryCache().subscribe((event) => {
    if (event.type === 'updated' && event.action.type === 'failed')
      failedAt ??= Date.now()
  })
  const result = client.fetchQuery({
    queryKey: ['retry-probe'],
    queryFn: getConfig,
  })
  await advance(100)
  expect(requests).toBe(1)
  expect(failedAt).toBeTypeOf('number')
  await advance(failedAt! + 2_999 - Date.now())
  expect(requests).toBe(1)
  await advance(1)
  expect(requests).toBe(2)
  expect(await result).toEqual(config)
  unsubscribe()
})

it.each([401, 403, 404, 422, 500])(
  'AD-018: HTTP %s không tự gửi lại',
  async (status) => {
    let requests = 0
    server.use(
      http.get('*/api/v1/config', () => {
        requests++
        return failure(status)
      }),
    )
    const client = setup()
    const result = client
      .fetchQuery({ queryKey: ['no-retry'], queryFn: getConfig })
      .catch((error: unknown) => error)
    await advance(10_000)
    expect(await result).toBeInstanceOf(ApiError)
    expect(requests).toBe(1)
  },
)

it.each(['busy', 'offline'] as const)(
  'AD-018: %s tối đa hai lần retry, mặc định chờ 2 giây',
  async (kind) => {
    let requests = 0
    server.use(
      http.get('*/api/v1/config', () => {
        requests++
        return kind === 'busy' ? failure(503) : HttpResponse.error()
      }),
    )
    const client = setup()
    let failedAt: number | undefined
    client.getQueryCache().subscribe((event) => {
      if (event.type === 'updated' && event.action.type === 'failed')
        failedAt ??= Date.now()
    })
    const result = client
      .fetchQuery({ queryKey: ['bounded-retry'], queryFn: getConfig })
      .catch((error: unknown) => error)
    await advance(100)
    expect(requests).toBe(1)
    await advance(failedAt! + 1_999 - Date.now())
    expect(requests).toBe(1)
    await advance(1)
    expect(requests).toBe(2)
    await advance(2_000)
    expect(requests).toBe(3)
    expect(await result).toBeInstanceOf(ApiError)
    await advance(20_000)
    expect(requests).toBe(3)
  },
)

it('AD-018: lỗi lập trình không bị coi là lỗi mạng có thể retry', async () => {
  const queryFn = vi.fn().mockRejectedValue(new Error('local failure'))
  const client = setup()
  const result = client
    .fetchQuery({ queryKey: ['unexpected'], queryFn })
    .catch((error: unknown) => error)
  await advance(10_000)
  expect(await result).toBeInstanceOf(Error)
  expect(queryFn).toHaveBeenCalledTimes(1)
})
