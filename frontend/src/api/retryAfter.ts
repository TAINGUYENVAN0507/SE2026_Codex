// Retry-After hỗ trợ số giây hoặc HTTP-date; null để caller chọn fallback.
export function retryAfterMs(
  value: string | null,
  now = Date.now(),
): number | null {
  if (!value?.trim()) return null
  const raw = value.trim()
  if (/^\d+(\.\d+)?$/.test(raw)) {
    const milliseconds = Number(raw) * 1_000
    return Number.isFinite(milliseconds)
      ? Math.min(milliseconds, 2_147_483_647)
      : null
  }
  if (!/[a-z]/i.test(raw)) return null
  const date = Date.parse(raw)
  return Number.isFinite(date)
    ? Math.max(0, Math.min(date - now, 2_147_483_647))
    : null
}
