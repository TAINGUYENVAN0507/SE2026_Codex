import { useMemo } from 'react'

// Gắn khóa với danh tính payload: retry giữ khóa, sửa metadata tạo khóa mới.
export function useIdempotencyKey(
  file: File | null,
  requestIdentity = '',
): string | null {
  const request = useMemo(
    () => ({
      identity: requestIdentity,
      key: file ? crypto.randomUUID() : null,
    }),
    [file, requestIdentity],
  )
  return request.key
}
