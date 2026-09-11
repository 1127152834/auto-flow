import { afterEach, expect, it, vi } from 'vitest'
import { createApiClient } from '../../shared/api/client'
import { createModelApi } from './api'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

it.each(['discovery', 'generation'] as const)('allows a slow %s response within the model provider timeout', async (operation) => {
  vi.useFakeTimers()
  const result = { message: '连接正常', items: [], outputPreview: 'OK' }
  vi.stubGlobal('fetch', vi.fn((_url: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((resolve, reject) => {
    const timer = setTimeout(() => resolve(Response.json(result)), operation === 'discovery' ? 12_000 : 20_000)
    init?.signal?.addEventListener('abort', () => {
      clearTimeout(timer)
      reject(init.signal?.reason)
    }, { once: true })
  })))

  const api = createModelApi(createApiClient('http://127.0.0.1:43127', 'test-token'))
  const request = operation === 'discovery'
    ? api.discoverModels('provider-1')
    : api.testModel('provider-1', { modelKey: 'model-1' })
  const completed = expect(request).resolves.toEqual(result)
  await vi.advanceTimersByTimeAsync(20_000)
  await completed
})
