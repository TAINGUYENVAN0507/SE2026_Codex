/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import contract from '../../../contracts/openapi.json'
import { errorMessageForCode, parseApiError } from './errors'

// OpenAPI hiện khai báo code là string; danh mục mã ổn định nằm ở error_codes.md.
const catalog = readFileSync(
  resolve(process.cwd(), '../contracts/error_codes.md'),
  'utf8',
)
const codes = [
  ...new Set([...catalog.matchAll(/^\| `([A-Z][A-Z_]+)`/gm)].map((m) => m[1])),
]

describe('FE-16: thông báo cho danh mục lỗi API', () => {
  it('reads the error envelope and a nonempty published catalog', () => {
    expect(contract.components.schemas.ErrorDetail.properties.code.type).toBe(
      'string',
    )
    expect(codes).toContain('SERVICE_UNAVAILABLE')
    expect(codes).toContain('AUDIO_EXPIRED')
  })
  it.each(codes)('localizes %s without exposing backend text', async (code) => {
    const error = await parseApiError(
      new Response(
        JSON.stringify({
          error: {
            code,
            message: 'CANARY_BACKEND_TRACE_PRIVATE',
            details: null,
          },
        }),
        { status: 400 },
      ),
    )
    expect(error.message).toBe(errorMessageForCode(code))
    expect(error.message).not.toBe(errorMessageForCode('UNKNOWN_ERROR'))
    expect(error.message).not.toContain('CANARY')
    expect(error.message).toMatch(/[à-ỹ]/i)
  })
})
