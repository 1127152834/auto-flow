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

it('preserves structured errors for risk confirmation and rate limiting', async () => {
  const error = { code: 'PROXYPANEL_RATE_LIMITED', message: '稍后重试', request_id: 'r1', field_errors: {}, retry_after_seconds: 12, outcome_unknown: false }
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error }), { status: 429 })))
  await expect(createApiClient('http://127.0.0.1:43127', 'secret').request('/api/v1/proxies')).rejects.toMatchObject({ status: 429, error })
})

it('supports a no-content delete response', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })))
  await expect(createApiClient('http://127.0.0.1:43127', 'secret').request('/api/v1/proxy-groups/g1', { method: 'DELETE' })).resolves.toBeUndefined()
})
