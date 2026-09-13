// @vitest-environment node
import { File as NodeFile, Blob as NodeBlob } from 'node:buffer'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createStudioHttpTransport } from '../api/http-transport'
import type { StudioTransport } from '../api/transport'
import { parseServerSentEvents } from '../../../shared/api/events'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

describe.each(['memory', 'http'])('authenticated Studio transport over %s', mode => {
  let server: Awaited<ReturnType<typeof startHttpStudioFixture>> | undefined
  let received: Request
  let handle: (request: Request) => Promise<Response>
  let request: StudioTransport
  let origin: string
  beforeEach(async () => {
    vi.stubGlobal('File', NodeFile); vi.stubGlobal('Blob', NodeBlob)
    const handler: StudioTransport = async input => { received = input as Request; return handle(received) }
    if (mode === 'http') server = await startHttpStudioFixture(handler)
    origin = server?.origin ?? 'http://autoflow-studio.mock'
    request = createStudioHttpTransport(origin, 'fixture-token', mode === 'http' ? fetch : handler)
  })
  afterEach(async () => { await server?.close(); server = undefined; vi.unstubAllGlobals() })
  it('applies the host token while preserving Request bodies, custom headers and error status', async () => {
    handle = async value => Response.json({ body: await value.json() }, { status: 422 })
    const response = await request(new Request(`${origin}/api/contract`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Custom': 'kept', 'X-AutoFlow-Token': 'untrusted', 'X-WebRPA-Token': 'obsolete' }, body: JSON.stringify({ value: '中文😀' }) }))
    expect(received.headers.get('x-autoflow-token')).toBe('fixture-token')
    expect(received.headers.get('x-webrpa-token')).toBeNull()
    expect(received.headers.get('x-custom')).toBe('kept')
    expect(response.status).toBe(422)
    expect(await response.json()).toEqual({ body: { value: '中文😀' } })
    expect(received.url).not.toContain('fixture-token')
  })
  it('preserves multipart file bytes without replacing the content boundary', async () => {
    handle = async value => {
      const form = await value.formData()
      const file = form.get('file') as File
      return Response.json({ name: file.name, contents: await file.text(), folder: form.get('folder') })
    }
    const form = new FormData()
    form.append('file', new File(['字节😀\u0000尾部'], 'fixture.txt'))
    form.append('folder', '图片资源')
    const response = await request(`${origin}/api/upload`, { method: 'POST', body: form })
    expect(await response.json()).toEqual({ name: 'fixture.txt', contents: '字节😀\u0000尾部', folder: '图片资源' })
    expect(received.headers.get('content-type')).toContain('multipart/form-data; boundary=')
  })
})
it('rejects foreign origins before invoking the network and does not retain legacy credentials', async () => {
  const fetcher = vi.fn<StudioTransport>(async () => new Response('ok'))
  const request = createStudioHttpTransport('http://127.0.0.1:1234', 'fixture-token', fetcher)
  await expect(request('http://127.0.0.1:1235/api/data')).rejects.toThrow('configured service')
  expect(fetcher).not.toHaveBeenCalled()
  await request('http://127.0.0.1:1234/api/data', { redirect: 'follow', credentials: 'include' })
  const sent = fetcher.mock.calls[0][0] as Request
  expect(sent.redirect).toBe('error')
  expect(sent.credentials).toBe('omit')
})
it('does not forward authentication to a redirect destination', async () => {
  const destination = vi.fn(async () => Response.json({ success: true }))
  const other = await startHttpStudioFixture(destination)
  const source = await startHttpStudioFixture(async () => new Response(null, { status: 302, headers: { location: `${other.origin}/api/target` } }))
  try {
    await expect(createStudioHttpTransport(source.origin, 'fixture-token')(`${source.origin}/api/redirect`)).rejects.toThrow()
    expect(destination).not.toHaveBeenCalled()
  } finally { await source.close(); await other.close() }
})
it('authenticates SSE and propagates cancellation while the stream is open', async () => {
  const source = await startHttpStudioFixture(async input => {
    expect((input as Request).headers.get('x-autoflow-token')).toBe('fixture-token')
    return new Response(new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode('id: 1\nevent: fixture\ndata: {"message":"中文"}\n\n')) } }), { headers: { 'content-type': 'text/event-stream' } })
  })
  const abort = new AbortController()
  try {
    const response = await createStudioHttpTransport(source.origin, 'fixture-token')(`${source.origin}/api/events/stream`, { signal: abort.signal })
    const iterator = parseServerSentEvents(response.body!)[Symbol.asyncIterator]()
    expect((await iterator.next()).value?.data).toBe('{"message":"中文"}')
    abort.abort()
    await expect(iterator.next()).rejects.toThrow()
    await vi.waitFor(() => expect(source.cancelledStreams).toBe(1))
  } finally { abort.abort(); await source.close() }
})
it('rejects missing authentication and malformed service origins at composition time', () => {
  expect(() => createStudioHttpTransport('http://localhost:1', ' ')).toThrow('token')
  expect(() => createStudioHttpTransport('http://localhost:1/api', 'fixture-token')).toThrow('origin')
})
