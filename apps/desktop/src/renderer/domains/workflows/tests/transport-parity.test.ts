import { File as NodeFile, Blob as NodeBlob } from 'node:buffer'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { parseServerSentEvents } from '../../../shared/api/events'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

describe.each(['memory', 'http'] as const)('shared protocol assertions: %s', mode => {
  let fixture: Awaited<ReturnType<typeof startHttpStudioFixture>> | undefined
  let server: typeof import('../api/mock-server')
  let request: (path: string, init?: RequestInit) => Promise<Response>
  const aborts: AbortController[] = []
  beforeEach(async () => {
    // The HTTP parser uses Node Web API files; jsdom File is a different realm.
    vi.stubGlobal('File', NodeFile)
    vi.stubGlobal('Blob', NodeBlob)
    const data = new Map<string, string>()
    vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
    vi.resetModules()
    server = await import('../api/mock-server')
    if (mode === 'http') {
      fixture = await startHttpStudioFixture(server.mockRequest)
      request = (path, init) => fetch(`${fixture!.origin}/api${path}`, init)
    } else request = (path, init) => server.mockRequest(`http://autoflow-studio.mock/api${path}`, init)
  })
  afterEach(async () => {
    aborts.splice(0).forEach(controller => controller.abort())
    server.configureMock({ offline: false, disconnect: true })
    await fixture?.close()
    fixture = undefined
    vi.unstubAllGlobals()
  })
  const json = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })

  it('preserves large Unicode documents, saved content on failure, and exact HTTP error codes', async () => {
    const content = { name: '协议往返', nodes: [{ id: 'web', type: 'input_text', data: { text: '中文😀'.repeat(18000) } }], edges: [], variables: [] }
    expect((await request('/local-workflows/save-to-folder', json({ filename: 'contract', content }))).status).toBe(200)
    expect((await (await request('/local-workflows/load/contract.json')).json()).content).toEqual(content)
    server.configureMock({ failNextSave: true })
    expect((await request('/local-workflows/save-to-folder', json({ filename: 'contract', content: { name: 'lost' } }))).status).toBe(507)
    expect((await (await request('/local-workflows/load/contract.json')).json()).content).toEqual(content)
    expect((await request('/workflows', { method: 'POST', body: '{broken' })).status).toBe(400)
    expect((await request('/unknown')).status).toBe(501)
  })
  it('round-trips scheduled configuration and fails missing workflows without a running record', async () => {
    const created = await request('/scheduled-tasks', json({ name: '计划 HTTP', workflow_id: 'missing.json', enabled: true, trigger: { type: 'startup', startup_delay: 0 } }))
    expect(created.status).toBe(200)
    const task = await created.json()
    expect(await (await request('/scheduled-tasks/list')).json()).toMatchObject([{ id: task.id, name: '计划 HTTP' }])
    expect((await request(`/scheduled-tasks/${task.id}/execute`, json({}))).status).toBe(404)
    expect(await (await request(`/scheduled-tasks/${task.id}/logs`)).json()).toEqual([])
    expect((await request(`/scheduled-tasks/${task.id}`, { method: 'DELETE' })).ok).toBe(true)
    expect(await (await request('/scheduled-tasks/list')).json()).toEqual([])
  })
  it('preserves multipart binary bytes and Unicode filenames over the actual upload contract', async () => {
    const boundary = 'autoflow-test-boundary'
    const bytes = Uint8Array.from({ length: 70000 }, (_, i) => i % 256)
    const encoder = new TextEncoder()
    const head = encoder.encode(`--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="测试.bin"\r\nContent-Type: application/octet-stream\r\n\r\n`)
    const tail = encoder.encode(`\r\n--${boundary}--\r\n`)
    const payload = new Uint8Array(head.length + bytes.length + tail.length)
    payload.set(head); payload.set(bytes, head.length); payload.set(tail, head.length + bytes.length)
    const response = await request('/image-assets/upload', { method: 'POST', headers: { 'content-type': `multipart/form-data; boundary=${boundary}` }, body: payload })
    expect(response.status, await response.clone().text()).toBe(200)
    const asset = await response.json()
    expect(asset.name).toBe('测试.bin')
    expect(asset.size).toBe(bytes.length)
    const decoded = Uint8Array.from(atob(asset.dataUrl.split(',')[1]), c => c.charCodeAt(0))
    expect(decoded).toEqual(bytes)
    expect(await (await request('/image-assets')).json()).toHaveLength(1)
    expect((await request('/image-assets/upload', { method: 'POST', headers: { 'content-type': 'multipart/form-data' }, body: 'broken' })).status).toBe(400)
    expect(await (await request('/image-assets')).json()).toHaveLength(1)
  })
  it('replays recording events without consuming them and keeps stop retries idempotent', async () => {
    await request('/browser/open', json({}))
    await request('/recorder/start', json({ sessionId: 'record-a' }))
    server.addMockRecordingEvent({ type: 'input', selector: '#name', value: '中文' })
    await request('/recorder/start', json({ sessionId: 'record-a' }))
    const first = await (await request('/recorder/events?sessionId=record-a&afterSeq=0')).json()
    expect(first).toMatchObject({ sessionId: 'record-a', nextSeq: 1, data: [{ sequence: 1, value: '中文' }] })
    expect(await (await request('/recorder/events?sessionId=record-a&afterSeq=0')).json()).toEqual(first)
    server.addMockRecordingEvent({ type: 'click', selector: '#tail' })
    const stop = await (await request('/recorder/stop', json({ sessionId: 'record-a', afterSeq: 1 }))).json()
    expect(stop.data.events).toMatchObject([{ sequence: 2, selector: '#tail' }])
    expect(await (await request('/recorder/stop', json({ sessionId: 'record-a', afterSeq: 1 }))).json()).toEqual(stop)
    expect((await request('/recorder/events?sessionId=wrong&afterSeq=0')).status).toBe(409)
    expect((await request('/recorder/events?sessionId=record-a&afterSeq=-1')).status).toBe(400)
    await request('/recorder/start', json({ sessionId: 'record-b' }))
    expect((await request('/recorder/start', json({ sessionId: 'record-a' }))).status).toBe(409)
    expect((await request('/recorder/stop', json({ sessionId: 'record-a' }))).status).toBe(409)
  })
  it('keeps command identity stable across retries and rejects changed payloads', async () => {
    const command = { commandId: 'stable', event: 'set_verbose_log', data: { enabled: true } }
    const first = await (await request('/events/commands', json(command))).json()
    expect(await (await request('/events/commands', json(command))).json()).toEqual(first)
    expect((await request('/events/commands', json({ ...command, data: { enabled: false } }))).status).toBe(409)
  })
  it('resumes numbered SSE with Unicode intact and cancels the previous stream', async () => {
    server.emitMockEvent('execution:log', { message: '第一条😀' })
    const abort = new AbortController(); aborts.push(abort)
    const result = await request('/events/stream?afterSeq=0', { signal: abort.signal })
    const events = parseServerSentEvents(result.body!)[Symbol.asyncIterator]()
    const first = (await events.next()).value!
    expect(first.id).toBe('1')
    expect(JSON.parse(first.data)).toEqual({ message: '第一条😀' })
    abort.abort()
    await events.return?.(undefined)
    if (fixture) await vi.waitFor(() => expect(fixture!.cancelledStreams).toBeGreaterThan(0))
    server.emitMockEvent('execution:log', { message: '断线期间' })
    const nextAbort = new AbortController(); aborts.push(nextAbort)
    const resumed = await request('/events/stream?afterSeq=1', { signal: nextAbort.signal })
    const replay = parseServerSentEvents(resumed.body!)[Symbol.asyncIterator]()
    const next = (await replay.next()).value!
    expect(next.id).toBe('2')
    expect(JSON.parse(next.data)).toEqual({ message: '断线期间' })
    nextAbort.abort()
    await replay.return?.(undefined)
  })

  it('reconnects the production event client without duplicates or manufactured completion', async () => {
    const { StudioEventClient } = await import('../api/event-client')
    const { setStudioTransport } = await import('../api/transport')
    const restore = setStudioTransport((input, init) => {
      const url = new URL(input instanceof Request ? input.url : String(input))
      return request(url.pathname.replace(/^\/api/, '') + url.search, init)
    })
    const client = new StudioEventClient('http://autoflow-studio.mock')
    const received = vi.fn(), completed = vi.fn()
    client.on('execution:log', received)
    client.on('execution:completed', completed)
    try {
      await vi.waitFor(() => expect(client.connected).toBe(true))
      server.emitMockEvent('execution:log', { message: 'connected' })
      await vi.waitFor(() => expect(received).toHaveBeenCalledTimes(1))
      server.configureMock({ disconnect: true })
      server.emitMockEvent('execution:log', { message: 'replay' })
      await vi.waitFor(() => expect(received).toHaveBeenCalledTimes(2), { timeout: 2500 })
      expect(received.mock.calls.map(args => args[0])).toEqual([{ message: 'connected' }, { message: 'replay' }])
      expect(completed).not.toHaveBeenCalled()
    } finally { client.disconnect(); restore() }
  })
})
