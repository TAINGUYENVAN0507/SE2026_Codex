import { afterEach, expect, it, vi } from 'vitest'
import { getJob } from '../../api/client'
import { onNetworkFailure } from '../../api/networkEvents'

afterEach(() => vi.restoreAllMocks())
it('cancelled job polling does not report a network outage', async () => {
  const failure = vi.fn()
  const unsubscribe = onNetworkFailure(failure)
  const cancelled = new DOMException('Cancelled', 'AbortError')
  vi.spyOn(globalThis, 'fetch').mockRejectedValue(cancelled)
  try {
    await expect(
      getJob('synthetic-job', new AbortController().signal),
    ).rejects.toMatchObject({ name: 'AbortError' })
    expect(failure).not.toHaveBeenCalled()
  } finally {
    unsubscribe()
  }
})
