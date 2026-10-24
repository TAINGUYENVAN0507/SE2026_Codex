import { describe, expect, it } from 'vitest'
import { createDevProxy } from './proxyConfig'

describe('FE-02 dev API proxy', () => {
  it('keeps the API path and defaults to the local backend', () => {
    expect(createDevProxy({})).toEqual({
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    })
  })

  it('uses the configured backend without rewriting the API prefix', () => {
    expect(
      createDevProxy({ VITE_API_PROXY_TARGET: 'http://localhost:8010' }),
    ).toEqual({
      '/api': { target: 'http://localhost:8010', changeOrigin: true },
    })
  })
})
