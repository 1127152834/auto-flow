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
