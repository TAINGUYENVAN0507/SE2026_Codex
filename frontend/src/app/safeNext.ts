const FALLBACK_PATH = '/meetings'

export function safeNext(value: string | null | undefined): string {
  if (
    !value ||
    !value.startsWith('/') ||
    value.startsWith('//') ||
    value.includes('\\') ||
    /%2f|%5c/i.test(value)
  )
    return FALLBACK_PATH

  return value
}
