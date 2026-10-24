import { useQuery } from '@tanstack/react-query'
import { getMe } from '../../api/client'
import { ApiError } from '../../api/errors'

export const ME_QUERY_KEY = ['me'] as const

export function useMe() {
  return useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => {
      try {
        return await getMe()
      } catch (error) {
        if (error instanceof ApiError && error.code === 'UNAUTHENTICATED')
          return null
        throw error
      }
    },
    retry: false,
    staleTime: 30_000,
  })
}
