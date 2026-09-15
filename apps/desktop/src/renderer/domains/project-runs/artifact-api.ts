import type { StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'

type Schema = components['schemas']
const encode = encodeURIComponent

export function createTaskArtifactApi(client: StreamingApiClient, projectId: string, taskId: string) {
  const base = `/api/v1/projects/${encode(projectId)}/tasks/${encode(taskId)}/artifacts`
  return {
    list: (page: number, signal?: AbortSignal) => client.request<Schema['RunArtifactPage']>(`${base}?page=${page}&pageSize=100`, { signal }),
    get: (artifactId: string, signal?: AbortSignal) => client.request<Schema['RunArtifactView']>(`${base}/${encode(artifactId)}`, { signal }),
    content: async (artifactId: string, signal?: AbortSignal): Promise<Blob> => {
      const response = await client.stream(`${base}/${encode(artifactId)}/content`, { signal })
      if (response.headers.get('content-type')?.split(';', 1)[0].trim() !== 'image/png') {
        throw new Error('截图响应格式无效')
      }
      return response.blob()
    },
  }
}
