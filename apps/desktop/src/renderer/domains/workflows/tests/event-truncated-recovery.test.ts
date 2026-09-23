import { expect, it, vi } from 'vitest'
import { StudioEventClient } from '../api/event-client'
import { setStudioTransport, type StudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

it.each(['memory', 'http'])('does not acknowledge an unterminated event before replay over %s', async mode => {
  const cursors: string[] = []
  const handler: StudioTransport = async input => {
    const url = new URL(input instanceof Request ? input.url : String(input))
    cursors.push(url.searchParams.get('afterSeq') ?? '')
    const text = cursors.length === 1
      ? 'id: 1\nevent: fixture:item\ndata: {"value":"未确认"}\n'
      : 'id: 1\nevent: fixture:item\ndata: {"value":"已确认"}\n\n'
    return new Response(text, { headers: { 'Content-Type': 'text/event-stream' } })
  }
  const fixture = mode === 'http' ? await startHttpStudioFixture(handler) : undefined
  setStudioTransport(fixture ? fetch : handler)
  const client = new StudioEventClient(fixture?.origin ?? 'http://autoflow-studio.mock')
  const values: string[] = []
  client.on('fixture:item', (value: { value: string }) => { values.push(value.value) })
  try {
    await vi.waitFor(() => expect(cursors.length).toBeGreaterThanOrEqual(2), { timeout: 2500 })
    await vi.waitFor(() => expect(values).toEqual(['已确认']))
    expect(cursors.slice(0, 2)).toEqual(['0', '0'])
  } finally { client.disconnect(); await fixture?.close(); setStudioTransport(mockRequest) }
})

it('keeps scoped stream cursors contiguous across hidden foreign run events and reconnect', async () => {
  vi.stubGlobal('location', { search: '?projectId=project-a' })
  const requests: URL[] = []
  const server = await startHttpStudioFixture(async input => {
    const url = new URL(input instanceof Request ? input.url : String(input))
    requests.push(url)
    const text = url.searchParams.get('afterSeq') === '0'
      ? 'id: 1\nevent: studio:cursor\ndata: {}\n\nid: 2\nevent: execution:log\ndata: {"message":"own"}\n\n'
      : 'id: 3\nevent: execution:completed\ndata: {"runId":"own-run"}\n\n'
    return new Response(text, { headers: { 'Content-Type': 'text/event-stream' } })
  })
  const restore = setStudioTransport(fetch)
  const client = new StudioEventClient(server.origin)
  const logs = vi.fn()
  const completed = vi.fn()
  client.on('execution:log', logs)
  client.on('execution:completed', completed)
  try {
    await vi.waitFor(() => expect(completed).toHaveBeenCalledTimes(1), { timeout: 2500 })
    expect(logs).toHaveBeenCalledTimes(1)
    expect(requests.slice(0, 2).map(url => url.searchParams.get('afterSeq'))).toEqual(['0', '2'])
    expect(requests.every(url => url.searchParams.get('projectId') === 'project-a')).toBe(true)
  } finally { client.disconnect(); restore(); vi.unstubAllGlobals(); await server.close() }
})
