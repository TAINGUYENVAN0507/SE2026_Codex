import { useEffect, useState } from 'react'

export function useObjectUrl(file?: File | null) {
  const [url, setUrl] = useState<string>()
  useEffect(() => {
    const next = file ? URL.createObjectURL(file) : undefined
    // Resource state follows the effect-owned URL and is revoked on replacement/unmount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setUrl(next)
    return () => {
      if (next) URL.revokeObjectURL(next)
    }
  }, [file])
  return url
}
