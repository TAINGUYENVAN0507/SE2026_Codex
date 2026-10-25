import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'
import { authHandlers, resetMockAuth } from './auth'
import userMe from '../../../contracts/fixtures/api/user_me.json'

const server = setupServer(...authHandlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(resetMockAuth)
afterAll(() => server.close())

function login(password: string) {
  return fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: userMe.user.email, password }),
  })
}

describe('FE-02 MSW auth session', () => {
  it('returns 401 before login and for an incorrect password', async () => {
    expect((await fetch('/api/v1/auth/me')).status).toBe(401)
    const response = await login('incorrect')
    expect(response.status).toBe(401)
    expect(await response.json()).toMatchObject({
      error: { code: 'INVALID_CREDENTIALS' },
    })
  })

  it('returns the fixture after login and ends the session on logout', async () => {
    expect(await (await login('demo-password')).json()).toEqual(userMe)
    expect(await (await fetch('/api/v1/auth/me')).json()).toEqual(userMe)
    expect(
      (await fetch('/api/v1/auth/logout', { method: 'POST' })).status,
    ).toBe(204)
    expect((await fetch('/api/v1/auth/me')).status).toBe(401)
  })
})
