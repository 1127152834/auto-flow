import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState, type PropsWithChildren } from 'react'

export function QueryProvider({ children }: PropsWithChildren) {
  const [client] = useState(() => new QueryClient({ defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false },
    mutations: { retry: false, gcTime: 0 },
  } }))
  useEffect(() => () => { void client.cancelQueries(); client.clear() }, [client])
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
