import { expect, it, vi } from 'vitest'
import { StudioEventClient } from '../api/event-client'
import { mockRequest } from '../api/mock-server'
import { setStudioTransport, type StudioTransport } from '../api/transport'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

it.each(['memory', 'http'])('changes per-connection log delivery without resetting cursors or cancelling commands over %s', async mode => {
  const streams: { after: string | null; verbose: string | null; signal?: AbortSignal | null }[] = []
  let confirm: (() => void) | undefined
  const handler: StudioTransport = async (input, init) => {
    const url = new URL(input instanceof Request ? input.url : String(input))
    const signal = init?.signal ?? (input instanceof Request ? input.signal : undefined)
    if (url.pathname.endsWith('/commands')) {
      const body = input instanceof Request ? await input.json() : JSON.parse(String(init?.body))
      await new Promise<void>(resolve => { confirm = resolve })
      expect(signal?.aborted).toBe(false)
      return Response.json({ commandId: body.commandId, success: true })
    }
    streams.push({ after: url.searchParams.get('afterSeq'), verbose: url.searchParams.get('verboseLog'), signal })
    const id = streams.length
    return new Response(new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(`id: ${id}\nevent: fixture:item\ndata: {"id":${id}}\n\n`))
        signal?.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')), { once: true })
      },
    }), { headers: { 'Content-Type': 'text/event-stream' } })
  }
  const fixture = mode === 'http' ? await startHttpStudioFixture(handler) : undefined
  setStudioTransport(fixture ? fetch : handler)
  const client = new StudioEventClient(fixture?.origin ?? 'http://autoflow-studio.mock', { verboseLog: false })
  const received: number[] = []
  const errors = vi.fn()
  client.on('fixture:item', (item: { id: number }) => received.push(item.id))
  client.on('connect_error', errors)
  try {
    await vi.waitFor(() => expect(received).toEqual([1]))
    const pending = client.command('input_prompt_result', { requestId: 'request', value: 'value' }, 'original')
    await vi.waitFor(() => expect(confirm).toBeTypeOf('function'))
    client.setVerboseLog(true)
    await vi.waitFor(() => expect(received).toEqual([1, 2]))
    expect(streams.map(item => [item.after, item.verbose])).toEqual([['0', 'false'], ['1', 'true']])
    expect(streams[0].signal?.aborted).toBe(true)
    expect(errors).not.toHaveBeenCalled()
    confirm!()
    expect(await pending).toEqual({ commandId: 'original', success: true })
    client.setVerboseLog(true)
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(streams).toHaveLength(2)
    client.setVerboseLog(false)
    await vi.waitFor(() => expect(received).toEqual([1, 2, 3]))
    expect(streams[2]).toMatchObject({ after: '2', verbose: 'false' })
  } finally {
    confirm?.()
    client.disconnect()
    await fixture?.close()
    setStudioTransport(mockRequest)
  }
})

it.each(['memory', 'http'])('keeps concise and verbose consumers independent over the same journal on %s', async mode => {
  const { emitMockEvent, configureMock } = await import('../api/mock-server')
  const fixture = mode === 'http' ? await startHttpStudioFixture(mockRequest) : undefined
  setStudioTransport(fixture ? fetch : mockRequest)
  const concise = new StudioEventClient(fixture?.origin ?? 'http://autoflow-studio.mock', { verboseLog: false })
  const verbose = new StudioEventClient(fixture?.origin ?? 'http://autoflow-studio.mock', { verboseLog: true })
  const conciseLogs: string[] = [], verboseLogs: string[] = []
  const prefix = crypto.randomUUID()
  concise.on('execution:log', (data: { log: { id: string } }) => { if (data.log.id.startsWith(prefix)) conciseLogs.push(data.log.id) })
  verbose.on('execution:log', (data: { log: { id: string } }) => { if (data.log.id.startsWith(prefix)) verboseLogs.push(data.log.id) })
  try {
    await vi.waitFor(() => expect(concise.connected && verbose.connected).toBe(true))
    emitMockEvent('execution:log', { log: { id: `${prefix}-info`, level: 'info' } })
    emitMockEvent('execution:log', { log: { id: `${prefix}-user`, level: 'info', isUserLog: true } })
    await vi.waitFor(() => expect(verboseLogs).toEqual([`${prefix}-info`, `${prefix}-user`]))
    expect(conciseLogs).toEqual([`${prefix}-user`])
    concise.setVerboseLog(true)
    await vi.waitFor(() => expect(concise.connected).toBe(true))
    emitMockEvent('execution:log', { log: { id: `${prefix}-new`, level: 'info' } })
    await vi.waitFor(() => expect(conciseLogs).toEqual([`${prefix}-user`, `${prefix}-new`]))
    expect(verboseLogs).toEqual([`${prefix}-info`, `${prefix}-user`, `${prefix}-new`])
  } finally {
    concise.disconnect(); verbose.disconnect(); configureMock({ disconnect: true })
    await fixture?.close(); setStudioTransport(mockRequest)
  }
})

it('Studio startup and the persisted log control use the stream preference without obsolete global commands', async () => {
  const { socketService } = await import('../events')
  const { useWorkflowStore } = await import('../editor-store')
  const { configureStudioConnection } = await import('../api/config')
  const requests: { path: string; verbose: string | null; command?: string }[] = []
  const transport: StudioTransport = async (input, init) => {
    const url = new URL(input instanceof Request ? input.url : String(input))
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    requests.push({ path: url.pathname, verbose: url.searchParams.get('verboseLog'), command: body?.event })
    return mockRequest(input, init)
  }
  const previous = useWorkflowStore.getState().verboseLog
  socketService.disconnect()
  useWorkflowStore.setState({ verboseLog: false })
  const restore = configureStudioConnection('http://autoflow-studio.mock', transport)
  try {
    socketService.connect()
    await vi.waitFor(() => expect(socketService.isConnected()).toBe(true))
    expect(requests.find(item => item.path.endsWith('/stream'))?.verbose).toBe('false')
    useWorkflowStore.getState().setVerboseLog(true)
    await vi.waitFor(() => expect(requests.some(item => item.path.endsWith('/stream') && item.verbose === 'true')).toBe(true))
    expect(requests.some(item => item.command === 'set_verbose_log' || item.command === 'set_current_workflow')).toBe(false)
  } finally {
    socketService.disconnect()
    restore()
    useWorkflowStore.getState().setVerboseLog(previous)
  }
})

it('does not acknowledge buffered frames from the stream cancelled by a log-mode change', async () => {
  const cursors: string[] = []
  const frame = (id: number, event = 'fixture:item') => `id: ${id}\nevent: ${event}\ndata: {"id":${id}}\n\n`
  const handler: StudioTransport = async input => {
    const url = new URL(input instanceof Request ? input.url : String(input))
    cursors.push(url.searchParams.get('afterSeq')!)
    return new Response(cursors.length === 1 ? frame(1) + frame(2, 'studio:cursor') + frame(3) : frame(2) + frame(3), { headers: { 'Content-Type': 'text/event-stream' } })
  }
  setStudioTransport(handler)
  const client = new StudioEventClient('http://autoflow-studio.mock', { verboseLog: false })
  const values: number[] = []
  client.on('fixture:item', (item: {id: number}) => { values.push(item.id); if (item.id === 1) client.setVerboseLog(true) })
  try {
    await vi.waitFor(() => expect(cursors.length).toBeGreaterThan(1))
    expect(cursors.slice(0, 2)).toEqual(['0', '1'])
    expect(values).toEqual([1, 2, 3])
  } finally { client.disconnect(); setStudioTransport(mockRequest) }
})
