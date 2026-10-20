import { useMemo } from 'react'

export function useIdempotencyKey(file: File | null): string | null {
  return useMemo(() => (file ? crypto.randomUUID() : null), [file])
}
