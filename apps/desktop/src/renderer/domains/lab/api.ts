import type { ApiClient } from '../../shared/api/client'
import type { LayaRequest, LayaResult, LayaStatus } from './types'

export function createLayaApi(client: ApiClient) {
  return {
    status: () => client.request<LayaStatus>('/api/v1/lab/laya/status'),
    predict: (body: LayaRequest, signal?: AbortSignal) => client.request<LayaResult>(
      '/api/v1/lab/laya/predict', { method: 'POST', body, signal, timeoutMs: 660_000 },
    ),
  }
}
