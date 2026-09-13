import { expect, it, vi } from 'vitest'
import { StudioEventClient } from '../api/event-client'
import { mockRequest, configureMock } from '../api/mock-server'
import { setStudioTransport } from '../api/transport'
import { startHttpStudioFixture } from './fixtures/http-studio-server'
it('recovers an accepted command after the actual HTTP socket closes without its response', async () => {
  const calls: { url: string; method: string }[] = []
  const server = await startHttpStudioFixture((input, init) => {
    const request = input as Request
    calls.push({ url: request.url, method: request.method })
    return mockRequest(input, init)
  })
  server.dropNextResponse('/api/events/commands')
  setStudioTransport(fetch)
  const client = new StudioEventClient(server.origin)
  const result = vi.fn(), error = vi.fn()
  client.on('command_result', result); client.on('command_error', error)
  try {
    const commandId = client.emit('set_verbose_log', { enabled: true })
    await vi.waitFor(() => expect(result).toHaveBeenCalledWith(expect.objectContaining({ commandId, success: true, httpStatus: 200 })))
    expect(calls.filter(call => call.method === 'POST' && call.url.endsWith('/events/commands'))).toHaveLength(1)
    expect(calls.some(call => call.method === 'GET' && call.url.endsWith(`/events/commands/${commandId}`))).toBe(true)
    expect(error).not.toHaveBeenCalled()
  } finally {
    client.disconnect(); configureMock({ disconnect: true }); await server.close(); setStudioTransport(mockRequest)
  }
})
