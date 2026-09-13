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
