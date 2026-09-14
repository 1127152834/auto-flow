import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
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
  client?: StreamingApiClient
}

const ApiContext = createContext<ApiContextValue | null>(null)

export function ApiProvider({ baseUrl, token, instanceId, children, client: providedClient }: ApiProviderProps) {
  // App keys this provider by workspace. Query observers must retain their client
  // across a same-workspace reconnect; instance-scoped keys isolate remote facts.
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: { retry: 2, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  }))
  useEffect(() => () => { void queryClient.cancelQueries(); queryClient.clear() }, [queryClient])
  const value = useMemo<ApiContextValue>(() => {
    const client = providedClient ?? createApiClient({ baseUrl, token })
    return {
      instanceId,
      client,
      profiles: createProfilesApi(client),
      kernels: createKernelsApi(client),
      proxyOptions: createProxyOptionsApi(client),
    }
  }, [baseUrl, instanceId, token, providedClient])

  const previous = useRef({ client: value.client, instanceId })
  useEffect(() => {
    if (previous.current.client === value.client && previous.current.instanceId === instanceId) return
    previous.current = { client: value.client, instanceId }
    void queryClient.cancelQueries({ type: 'inactive' })
    // Some existing management consumers use stable keys. Reconnect must refresh
    // their remote facts too, without replacing observers or local form state.
    void queryClient.invalidateQueries({ type: 'active' }, { cancelRefetch: false })
  }, [queryClient, value.client, instanceId])

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
