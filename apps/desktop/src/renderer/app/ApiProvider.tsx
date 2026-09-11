import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { createKernelsApi, type KernelsApi } from '../domains/kernels/api'
import {
  createProfilesApi,
  createProxyOptionsApi,
  type ProfilesApi,
  type ProxyOptionsApi,
} from '../domains/profiles/api'
import { createApiClient, type StreamingApiClient } from '../shared/api/client'

export type ApiContextValue = {
  instanceId: string
  client: StreamingApiClient
  profiles: ProfilesApi
  kernels: KernelsApi
  proxyOptions: ProxyOptionsApi
}

export type ApiProviderProps = {
  baseUrl: string
  token: string
  instanceId: string
  children: ReactNode
}

const ApiContext = createContext<ApiContextValue | null>(null)

export function ApiProvider({ baseUrl, token, instanceId, children }: ApiProviderProps) {
  const queryClient = useMemo(() => new QueryClient({
    defaultOptions: {
      queries: { retry: 2, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  }), [instanceId])
  const value = useMemo<ApiContextValue>(() => {
    const client = createApiClient({ baseUrl, token })
    return {
      instanceId,
      client,
      profiles: createProfilesApi(client),
      kernels: createKernelsApi(client),
      proxyOptions: createProxyOptionsApi(client),
    }
  }, [baseUrl, instanceId, token])

  return (
    <ApiContext.Provider value={value}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ApiContext.Provider>
  )
}

export function useApi(): ApiContextValue {
  const value = useContext(ApiContext)
  if (!value) throw new Error('useApi must be used inside ApiProvider')
  return value
}
