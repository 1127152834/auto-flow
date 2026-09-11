import type { ApiClient } from '../../shared/api/client'
import type {
  ModelDiscoveryRead,
  ModelInput,
  ModelOptionListRead,
  ModelProviderConnectInput,
  ModelProviderConnectionUpdateInput,
  ModelProviderCreateInput,
  ModelProviderMetadataUpdateInput,
  ModelProviderListRead,
  ModelProviderRead,
  ModelRead,
  ModelTestInput,
  ModelTestRead,
} from './model'

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export type ModelApi = ReturnType<typeof createModelApi>

export function createModelApi(client: ApiClient) {
  return {
    listProviders: () => client.request<ModelProviderListRead>('/api/v1/model-providers'),
    getProvider: (id: string) => client.request<ModelProviderRead>(`/api/v1/model-providers/${id}`),
    previewConnection: (body: ModelProviderCreateInput) => client.request<ModelDiscoveryRead>('/api/v1/model-providers/connection-preview', json('POST', body)),
    connect: (body: ModelProviderConnectInput) => client.request<ModelProviderRead>('/api/v1/model-providers/connect', json('POST', body)),
    updateProvider: (id: string, body: ModelProviderMetadataUpdateInput) => client.request<ModelProviderRead>(`/api/v1/model-providers/${id}`, json('PUT', body)),
    updateConnection: (id: string, body: ModelProviderConnectionUpdateInput) => client.request<ModelProviderRead>(`/api/v1/model-providers/${id}/connection`, json('PUT', body)),
    removeProvider: (id: string) => client.request<void>(`/api/v1/model-providers/${id}`, { method: 'DELETE' }),
    testProvider: (id: string) => client.request<ModelDiscoveryRead>(`/api/v1/model-providers/${id}/test`, { method: 'POST' }),
    discoverModels: (id: string, signal?: AbortSignal) => client.request<ModelDiscoveryRead>(`/api/v1/model-providers/${id}/models/discover`, { signal }),
    testModel: (id: string, body: ModelTestInput) => client.request<ModelTestRead>(`/api/v1/model-providers/${id}/models/test`, json('POST', body)),
    createModel: (id: string, body: ModelInput) => client.request<ModelRead>(`/api/v1/model-providers/${id}/models`, json('POST', body)),
    updateModel: (id: string, body: ModelInput) => client.request<ModelRead>(`/api/v1/models/${id}`, json('PUT', body)),
    removeModel: (id: string) => client.request<void>(`/api/v1/models/${id}`, { method: 'DELETE' }),
    listOptions: () => client.request<ModelOptionListRead>('/api/v1/models/options'),
  }
}
