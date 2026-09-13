import { expect, it, vi } from 'vitest'
import { StudioEventClient } from '../api/event-client'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'
import type { StudioTransport } from '../api/transport'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

it.each(['memory', 'http'])('continues dispatching and advances the replay cursor after a listener throws over %s', async mode => {
  const requests: string[] = []
  const frame = (seq: number) => `id: ${seq}\nevent: fixture:item\ndata: {"seq":${seq}}\n\n`
  const handler: StudioTransport = async input => {
    const url = new URL(input instanceof Request ? input.url : String(input))
    const after = url.searchParams.get('afterSeq') ?? '0'
    requests.push(after)
    return new Response(after === '0' ? frame(1) + frame(2) : frame(3), { headers: { 'Content-Type': 'text/event-stream' } })
  }
  const fixture = mode === 'http' ? await startHttpStudioFixture(handler) : undefined
  setStudioTransport(fixture ? fetch : handler)
  const error = vi.spyOn(console, 'error').mockImplementation(() => {})
  const client = new StudioEventClient(fixture?.origin ?? 'http://autoflow-studio.mock')
  const received: number[] = []
  const broken = vi.fn(() => { throw new Error('fixture UI listener failed') })
  client.on('fixture:item', broken)
  client.on('fixture:item', (value: { seq: number }) => { received.push(value.seq) })
  try {
    await vi.waitFor(() => expect(received).toEqual([1, 2, 3]), { timeout: 2500 })
    expect(requests.slice(0, 2)).toEqual(['0', '2'])
    expect(broken).toHaveBeenCalledTimes(3)
    expect(error).toHaveBeenCalledTimes(3)
  } finally { client.disconnect(); await fixture?.close(); setStudioTransport(mockRequest); error.mockRestore() }
})
it('does not query an applied command again when a command-result subscriber throws', async () => {
  const requests: string[] = []
  setStudioTransport(async input => {
    const url = String(input)
    requests.push(url)
    if (url.endsWith('/commands')) return Response.json({ success: true })
    return new Response('', { headers: { 'Content-Type': 'text/event-stream' } })
  })
  const error = vi.spyOn(console, 'error').mockImplementation(() => {})
  const client = new StudioEventClient('http://autoflow-studio.mock')
  const confirmed = vi.fn()
  client.on('command_result', () => { throw new Error('broken result panel') })
  client.on('command_result', confirmed)
  try {
    client.emit('fixture:command', {}, '00000000-0000-4000-8000-000000000001')
    await vi.waitFor(() => expect(confirmed).toHaveBeenCalledOnce())
    expect(requests.some(url => url.endsWith('/commands/00000000-0000-4000-8000-000000000001'))).toBe(false)
  } finally { client.disconnect(); setStudioTransport(mockRequest); error.mockRestore() }
})
