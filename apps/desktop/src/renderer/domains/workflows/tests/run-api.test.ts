import { afterEach, expect, it, vi } from 'vitest'
import { createApiClient } from '../../../shared/api/client'
import { createWorkflowRunApi } from '../run-api'
import { runEvent } from './run-fixtures'

afterEach(() => vi.unstubAllGlobals())

it('reads artifacts using authenticated headers without exposing the token in the image URL', async () => {
  const request = vi.fn<typeof fetch>(async () => new Response('png bytes', { headers: { 'content-type': 'image/png' } }))
  vi.stubGlobal('fetch', request)
  const api = createWorkflowRunApi(createApiClient('http://127.0.0.1:5000', 'private-studio-token'))
  const blob = await api.artifact('run-1', 'shot-1')
  expect(blob.type).toBe('image/png')
  expect(request).toHaveBeenCalledWith('http://127.0.0.1:5000/api/v1/workflows/runs/run-1/artifacts/shot-1', expect.objectContaining({ headers: { 'x-autoflow-token': 'private-studio-token' } }))
  expect(String(request.mock.calls[0][0])).not.toContain('private-studio-token')
})

it('resumes SSE from the committed cursor and parses actual run_event envelopes', async () => {
  const event = runEvent(7)
  vi.stubGlobal('fetch', vi.fn(async () => new Response(`: keepalive\n\nevent: run_event\nid: 7\ndata: ${JSON.stringify(event)}\n\n`, { headers: { 'content-type': 'text/event-stream' } })))
  const api = createWorkflowRunApi(createApiClient('http://127.0.0.1:5000', 'token'))
  const onEvent = vi.fn()
  await api.watch('run-1', 6, new AbortController().signal, onEvent)
  expect(fetch).toHaveBeenCalledWith('http://127.0.0.1:5000/api/v1/workflows/runs/run-1/stream?afterSeq=6', expect.objectContaining({ headers: { accept: 'text/event-stream', 'x-autoflow-token': 'token' } }))
  expect(onEvent).toHaveBeenCalledExactlyOnceWith(event)
})
