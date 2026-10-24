export function createDevProxy(env: Record<string, string | undefined>) {
  return {
    '/api': {
      target: env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
      changeOrigin: true,
    },
  }
}
