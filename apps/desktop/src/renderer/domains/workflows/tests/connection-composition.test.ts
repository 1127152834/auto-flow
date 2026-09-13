import { expect, it, vi } from 'vitest'
import { apiRequest, getApiBaseUrl } from '../api'
import { configureStudioConnection, getBackendBaseUrl } from '../api/config'
import { studioFetch } from '../api/transport'
import { StudioEventClient } from '../api/event-client'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

it('uses the composed connection for service requests and direct tool requests, then restores it', async () => {
  const previous = getBackendBaseUrl()
  const calls: string[] = []
  const restore = configureStudioConnection('http://127.0.0.1:32123/', async input => {
    calls.push(String(input))
    return Response.json({ success: true, value: 'composed' })
  })
  try {
    expect(getApiBaseUrl()).toBe('http://127.0.0.1:32123/api')
    expect((await apiRequest('/composition')).success).toBe(true)
    expect((await studioFetch(`${getBackendBaseUrl()}/api/tool`)).ok).toBe(true)
    expect(calls).toEqual(['http://127.0.0.1:32123/api/composition', 'http://127.0.0.1:32123/api/tool'])
  } finally { restore() }
  expect(getApiBaseUrl()).toBe(`${previous}/api`)
})

it.each(['file:///tmp/service', 'http://user:secret@localhost', 'http://localhost/api', 'http://localhost/?token=a', 'http://localhost/#fragment', 'not a URL'])(
  'rejects invalid connection %s without replacing the active transport', async origin => {
    const adapter = vi.fn(async () => Response.json({ success: true }))
    const restore = configureStudioConnection('http://127.0.0.1:32124', adapter)
    try {
      expect(() => configureStudioConnection(origin, fetch)).toThrow()
      expect(getBackendBaseUrl()).toBe('http://127.0.0.1:32124')
      await apiRequest('/still-connected')
      expect(adapter).toHaveBeenCalledTimes(1)
    } finally { restore() }
  },
)

it('uses actual HTTP for the same service consumer and incremental SSE consumer', async () => {
  const requests: string[] = []
  const server = await startHttpStudioFixture(async input => {
    const path = new URL((input as Request).url).pathname
    requests.push(path)
    if (path.endsWith('/stream')) return new Response('id: 1\nevent: composition\ndata: {"value":"分块响应"}\n\n', { headers: { 'Content-Type': 'text/event-stream' } })
    return Response.json({ success: true, source: 'local-http' })
  })
  const restore = configureStudioConnection(server.origin, fetch)
  const client = new StudioEventClient(getBackendBaseUrl())
  const received = vi.fn()
  client.on('composition', received)
  try {
    const response = await apiRequest<{ source: string }>('/composition')
    expect(response.success).toBe(true)
    expect(response.data?.source).toBe('local-http')
    await vi.waitFor(() => expect(received).toHaveBeenCalledWith({ value: '分块响应' }))
    expect(requests).toContain('/api/composition')
    expect(requests).toContain('/api/events/stream')
  } finally { client.disconnect(); restore(); await server.close() }
})

it('does not silently select a fixture before connection composition', async () => {
  vi.resetModules()
  const config = await import('../api/config')
  expect(() => config.getBackendBaseUrl()).toThrow('has not been configured')
})
