import { useMemo } from 'react'

// Gắn khóa với payload: thử lại giữ khóa, đổi metadata cấp khóa mới.
export function useIdempotencyKey(
  file: File | null,
  requestIdentity = '',
): string | null {
  return useMemo(
    () => (file ? crypto.randomUUID() : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- FE-05: metadata đổi phải tạo khóa mới dù callback chỉ đọc file.
    [file, requestIdentity],
  )
}
