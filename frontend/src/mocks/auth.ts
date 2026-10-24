import { http, HttpResponse } from 'msw'
import userMe from '../../../contracts/fixtures/api/user_me.json'

let signedIn = false

export function resetMockAuth() {
  signedIn = false
}

export const authHandlers = [
  http.post('*/api/v1/auth/login', async ({ request }) => {
    const body = (await request.json()) as { email?: string; password?: string }
    // Thông tin giả dành riêng cho MSW, không phải tài khoản backend.
    if (body.email !== userMe.user.email || body.password !== 'demo-password')
      return HttpResponse.json(
        {
          error: {
            code: 'INVALID_CREDENTIALS',
            message: 'Email hoặc mật khẩu không chính xác.',
            details: null,
            request_id: null,
          },
        },
        { status: 401 },
      )
    signedIn = true
    return HttpResponse.json(userMe)
  }),
  http.get('*/api/v1/auth/me', () =>
    signedIn
      ? HttpResponse.json(userMe)
      : HttpResponse.json(
          {
            error: {
              code: 'UNAUTHENTICATED',
              message: 'Bạn chưa đăng nhập.',
              details: null,
              request_id: null,
            },
          },
          { status: 401 },
        ),
  ),
  http.post('*/api/v1/auth/logout', () => {
    signedIn = false
    return new HttpResponse(null, { status: 204 })
  }),
]
