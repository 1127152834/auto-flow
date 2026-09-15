import { expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../shared/api/client'
import { createTaskArtifactApi } from './artifact-api'

function client(request = vi.fn(), stream = vi.fn()): StreamingApiClient {
  return { request, stream, health: vi.fn() } as StreamingApiClient
}

it('uses project-scoped encoded artifact routes', async () => {
  const signal = new AbortController().signal
  const request = vi.fn().mockResolvedValue({ items: [], page: 2, pageSize: 100, total: 0, sort: 'createdAt' })
  const api = createTaskArtifactApi(client(request), 'project/one', 'task two')

  await api.list(2, signal)
  await api.get('artifact/three', signal)

  expect(request).toHaveBeenNthCalledWith(1, '/api/v1/projects/project%2Fone/tasks/task%20two/artifacts?page=2&pageSize=100', { signal })
  expect(request).toHaveBeenNthCalledWith(2, '/api/v1/projects/project%2Fone/tasks/task%20two/artifacts/artifact%2Fthree', { signal })
})

it('loads screenshot bytes through the authenticated streaming client', async () => {
  const body = new Blob(['png'], { type: 'image/png' })
  const stream = vi.fn().mockResolvedValue(new Response(body, { headers: { 'content-type': 'image/png' } }))
  const signal = new AbortController().signal

  await expect(createTaskArtifactApi(client(vi.fn(), stream), 'project', 'task').content('artifact', signal)).resolves.toEqual(body)
  expect(stream).toHaveBeenCalledWith('/api/v1/projects/project/tasks/task/artifacts/artifact/content', { signal })
})
