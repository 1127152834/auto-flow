import { afterEach, expect, it, vi } from 'vitest'
import { createApiClient } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

it('adds the sidecar token to every request', async () => {
  const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    expect(init?.headers).toEqual({ 'x-autoflow-token': 'secret' })
    return new Response(JSON.stringify({
      status: 'ok',
      apiVersion: 'v1',
      instanceId: 'test',
    }), { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)

  await expect(createApiClient('http://127.0.0.1:43127', 'secret').health()).resolves.toEqual({
    status: 'ok',
    apiVersion: 'v1',
    instanceId: 'test',
  })

  expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:43127/health', {
    headers: { 'x-autoflow-token': 'secret' },
  })
})


it('preserves structured error metadata without retaining request content', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ error: {
    code: 'MODEL_EXISTS', message: '模型已存在', details: { fields: { modelKey: '重复' } }, requestId: 'test-request',
  } }, { status: 409 })))
  await expect(createApiClient('http://localhost', 'secret').request('/api/v1/models/sample')).rejects.toMatchObject({
    message: '模型已存在', status: 409, code: 'MODEL_EXISTS', details: { fields: { modelKey: '重复' } }, requestId: 'test-request',
  })
})

it('handles successful empty deletion and forwards cancellation', async () => {
  const signal = new AbortController().signal
  const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
  vi.stubGlobal('fetch', fetchMock)
  await expect(createApiClient('http://localhost', 'test-token').request<void>('/api/v1/models/sample', { method: 'DELETE', signal })).resolves.toBeUndefined()
  expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'DELETE', signal, headers: { 'x-autoflow-token': 'test-token' } })
})

it.each(['<h1>private upstream content</h1>', JSON.stringify({ detail: 'private upstream content' }), JSON.stringify({ error: 'private upstream content' })])('uses a safe message for malformed error bodies', async (body) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 502 })))
  await expect(createApiClient('http://localhost', 'test-token').request('/api/v1/models/options')).rejects.toMatchObject({
    message: 'API request failed with status 502', status: 502,
  })
})
