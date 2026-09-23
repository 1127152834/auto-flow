import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

type Schema = components['schemas']
export type RunAsset = Schema['StudioProjectRunAsset']
export type AssetQuery = { kind: '' | RunAsset['kind']; runId: string; nodeId: string; cursor: number }

export function createProjectRunAssetsApi(client: StreamingApiClient, projectId: string) {
  const encode = encodeURIComponent
  const scope = `projectId=${encode(projectId)}`
  return {
    list: async (query: AssetQuery, signal?: AbortSignal) => {
      const params = new URLSearchParams({ cursor: String(query.cursor), limit: '50' })
      for (const key of ['kind', 'runId', 'nodeId'] as const) if (query[key]) params.set(key, query[key])
      const page = await client.request<Schema['StudioProjectRunAssetPage']>(`/api/v1/projects/${encode(projectId)}/run-assets?${params}`, { signal })
      if (page.items.some(item => item.projectId !== projectId)) throw new ApiClientError('运行数据不属于当前项目', 409, 'RUN_ASSET_PROJECT_MISMATCH')
      return page
    },
    content: async (asset: RunAsset, signal?: AbortSignal) => {
      if (asset.projectId !== projectId) throw new ApiClientError('运行数据不属于当前项目', 409, 'RUN_ASSET_PROJECT_MISMATCH')
      const base = `/api/workflow-runs/${encode(asset.runId)}`
      if (asset.kind === 'result') {
        const result = await client.request<Schema['StudioRunResultRow']>(`${base}/results/${asset.sequence}?${scope}`, { signal })
        if (result.sequence !== asset.sequence || result.nodeId !== asset.nodeId) throw new ApiClientError('结果身份不匹配', 409, 'RUN_ASSET_IDENTITY_MISMATCH')
        return new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
      }
      const response = await client.stream(`${base}/artifacts/${encode(asset.artifactId!)}?${scope}`, { signal })
      const blob = await response.blob()
      if (asset.size !== null && asset.size !== blob.size) throw new ApiClientError('产物大小不一致', 409, 'RUN_ASSET_SIZE_MISMATCH')
      if (asset.sha256) {
        const hash = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())
        const hex = [...new Uint8Array(hash)].map(byte => byte.toString(16).padStart(2, '0')).join('')
        if (hex !== asset.sha256) throw new ApiClientError('产物内容校验失败', 409, 'RUN_ASSET_HASH_MISMATCH')
      }
      return blob
    },
    logs: (asset: RunAsset, cursor: number, signal?: AbortSignal) => client.request<Schema['StudioExecutionLogPage']>(
      `/api/workflow-runs/${encode(asset.runId)}/logs?${scope}&nodeId=${encode(asset.nodeId)}${asset.executionId ? `&executionId=${encode(asset.executionId)}` : ''}&cursor=${cursor}&limit=100`, { signal }),
  }
}
