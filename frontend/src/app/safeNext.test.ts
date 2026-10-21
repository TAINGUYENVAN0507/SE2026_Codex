import { describe, expect, it } from 'vitest'
import { safeNext } from './safeNext'

describe('safeNext', () => {
  it('accepts an internal path with query and hash', () => {
    expect(safeNext('/meetings/new?from=home#upload')).toBe(
      '/meetings/new?from=home#upload',
    )
  })

  it.each([
    '//evil.com',
    'https://evil.com',
    'javascript:alert(1)',
    '/\\evil.com',
    '/%2f%2fevil.com',
    '',
    null,
  ])('falls back for unsafe next value %s', (value) => {
    expect(safeNext(value)).toBe('/meetings')
  })
})
