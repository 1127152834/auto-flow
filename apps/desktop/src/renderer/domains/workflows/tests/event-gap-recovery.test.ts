import { expect, it, vi } from 'vitest'
import { StudioEventClient } from '../api/event-client'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'
import type { StudioTransport } from '../api/transport'
import { startHttpStudioFixture } from './fixtures/http-studio-server'
const frame = (id: number) => `id: ${id}\nevent: fixture:item\ndata: {"id":${id}}\n\n`
it.each(['memory', 'http'])('replays a sequence gap from the last confirmed event over %s', async mode => {
  const requests: { after: string | null; signal?: AbortSignal | null }[] = []
  const handler: StudioTransport = async (input, init) => {
    const url = new URL(input instanceof Request ? input.url : String(input))
    requests.push({ after: url.searchParams.get('afterSeq'), signal: init?.signal ?? (input instanceof Request ? input.signal : undefined) })
    return new Response(requests.length === 1 ? frame(1) + frame(3) : frame(2) + frame(3), { headers: { 'Content-Type': 'text/event-stream' } })
  }
  const fixture = mode === 'http' ? await startHttpStudioFixture(handler) : undefined
  setStudioTransport(fixture ? fetch : handler)
  const client = new StudioEventClient(fixture?.origin ?? 'http://autoflow-studio.mock')
  const received: number[] = []
  client.on('fixture:item', (value: { id: number }) => { received.push(value.id) })
  try {
    await vi.waitFor(() => expect(received).toEqual([1, 2, 3]), { timeout: 2500 })
    expect(requests.slice(0, 2).map(request => request.after)).toEqual(['0', '1'])
    expect(requests[0].signal?.aborted).toBe(true)
  } finally { client.disconnect(); await fixture?.close(); setStudioTransport(mockRequest) }
})

it.each(['memory', 'http'])('resets only an explicitly expired service-generation cursor over %s', async mode => {
  const cursors: string[] = []
  const handler: StudioTransport = async input => {
    const url = new URL(input instanceof Request ? input.url : String(input))
    const cursor = url.searchParams.get('afterSeq') ?? ''
    cursors.push(cursor)
    if (cursors.length === 1) return new Response(frame(1) + frame(2), { headers: { 'Content-Type': 'text/event-stream' } })
    if (cursors.length === 2) return Response.json({ error: { code: 'EVENT_CURSOR_AHEAD', message: '事件游标超过当前服务连接代次', details: { afterSeq: 2, latestSeq: 0 } } }, { status: 409 })
    return new Response(frame(1), { headers: { 'Content-Type': 'text/event-stream' } })
  }
  const fixture = mode === 'http' ? await startHttpStudioFixture(handler) : undefined
  setStudioTransport(fixture ? fetch : handler)
  const client = new StudioEventClient(fixture?.origin ?? 'http://autoflow-studio.mock')
  const received: number[] = []
  client.on('fixture:item', (value: { id: number }) => { received.push(value.id) })
  try {
    await vi.waitFor(() => expect(received).toEqual([1, 2, 1]), { timeout: 4000 })
    expect(cursors.slice(0, 3)).toEqual(['0', '2', '0'])
  } finally { client.disconnect(); await fixture?.close(); setStudioTransport(mockRequest) }
})
