import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type PropsWithChildren } from 'react'
import { BrowserRouter } from 'react-router-dom'
import { ApiError } from '../api/errors'

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        retry: (failureCount, error) =>
          failureCount < 2 &&
          error instanceof ApiError &&
          (error.status === 503 || error.code === 'NETWORK_ERROR'),
        retryDelay: (_attempt, error) =>
          error instanceof ApiError ? (error.retryAfterMs ?? 2_000) : 2_000,
        staleTime: 30_000,
      },
      mutations: {
        retry: false,
      },
    },
  })
}

export function AppProviders({ children }: PropsWithChildren) {
  const [queryClient] = useState(createQueryClient)

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  )
}
