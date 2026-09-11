import { afterEach, expect, it, vi } from 'vitest'
import { createApiClient, type ApiClient } from '../../shared/api/client'
import { createProxyApi, type ConnectionView } from './api'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

it('gives only remote proxy actions a 60 second request budget', () => {
  const request = vi.fn()
  const api = createProxyApi({ request, health: vi.fn() } as unknown as ApiClient)
  const connection = { id: 'connection-1', revision: 2 } as ConnectionView

  api.createConnection('ProxyPanel', 'secret')
  api.replaceApiKey(connection, 'replacement')
  api.sync(connection.id)
  api.probeProxy('proxy-1')
  api.updateConnection(connection, 'Local rename')

  expect(request.mock.calls.slice(0, 4).every(([, init]) => init.timeoutMs === 60_000)).toBe(true)
  expect(request.mock.calls[4][1].timeoutMs).toBeUndefined()
})

it('allows a real client request to spend over ten seconds on fetch and response body', async () => {
  vi.useFakeTimers()
  let requestSignal: AbortSignal | undefined
  vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
    requestSignal = init?.signal ?? undefined
    return new Promise<Response>((resolve, reject) => {
      const connectTimer = window.setTimeout(() => {
        resolve(new Response(new ReadableStream({
          start(controller) {
            const bodyTimer = window.setTimeout(() => {
              controller.enqueue(new TextEncoder().encode('{"id":"connection-1"}'))
              controller.close()
            }, 11_000)
            requestSignal?.addEventListener('abort', () => {
              window.clearTimeout(bodyTimer)
              controller.error(requestSignal?.reason)
            }, { once: true })
          },
        }), { status: 201 }))
      }, 11_000)
      requestSignal?.addEventListener('abort', () => {
        window.clearTimeout(connectTimer)
        reject(requestSignal?.reason)
      }, { once: true })
    })
  }))

  let settled = false
  const result = createProxyApi(createApiClient('http://127.0.0.1:43127', 'secret'))
    .createConnection('ProxyPanel', 'secret')
    .then(
      (value) => { settled = true; return { value } },
      (error: unknown) => { settled = true; return { error } },
    )

  await vi.advanceTimersByTimeAsync(10_001)
  expect(requestSignal?.aborted).toBe(false)
  expect(settled).toBe(false)

  await vi.advanceTimersByTimeAsync(11_999)
  await expect(result).resolves.toMatchObject({ value: { id: 'connection-1' } })
})
