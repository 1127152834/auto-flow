import type { StreamingApiClient } from './client'
import type { KernelOperation } from './types'

export type ServerSentEvent = {
  event: string
  data: string
  id?: string
}

export type KernelEventSnapshot = {
  type: 'snapshot'
  operations: KernelOperation[]
}

export type KernelEventStreamOptions = {
  signal: AbortSignal
  onSnapshot(snapshot: KernelEventSnapshot): void
  onError?(error: unknown): void
  reconnectDelays?: readonly number[]
}

export async function* parseServerSentEvents(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<ServerSentEvent> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let event = 'message'
  let data: string[] = []
  let id: string | undefined

  function dispatch(): ServerSentEvent | undefined {
    if (data.length === 0) return undefined
    const value = { event, data: data.join('\n'), ...(id === undefined ? {} : { id }) }
    event = 'message'
    data = []
    return value
  }

  function consume(line: string): ServerSentEvent | undefined {
    if (line === '') return dispatch()
    if (line.startsWith(':')) return undefined
    const separator = line.indexOf(':')
    const field = separator < 0 ? line : line.slice(0, separator)
    let value = separator < 0 ? '' : line.slice(separator + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
    else if (field === 'id' && !value.includes('\0')) id = value
    return undefined
  }

  try {
    while (true) {
      const chunk = await reader.read()
      if (chunk.done) break
      buffer += decoder.decode(chunk.value, { stream: true })
      let newline = buffer.indexOf('\n')
      while (newline >= 0) {
        const rawLine = buffer.slice(0, newline)
        buffer = buffer.slice(newline + 1)
        const parsed = consume(rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine)
        if (parsed) yield parsed
        newline = buffer.indexOf('\n')
      }
    }
    buffer += decoder.decode()
    if (buffer) {
      const parsed = consume(buffer.endsWith('\r') ? buffer.slice(0, -1) : buffer)
      if (parsed) yield parsed
    }
    const parsed = dispatch()
    if (parsed) yield parsed
  } finally {
    reader.releaseLock()
  }
}

function snapshotFrom(event: ServerSentEvent): KernelEventSnapshot | undefined {
  if (event.event !== 'snapshot') return undefined
  try {
    const value = JSON.parse(event.data) as Record<string, unknown>
    if (value.type !== 'snapshot' || !Array.isArray(value.operations)) return undefined
    return value as KernelEventSnapshot
  } catch {
    return undefined
  }
}

function wait(delay: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return Promise.resolve()
  return new Promise((resolve) => {
    const timer = window.setTimeout(done, delay)
    function done() {
      window.clearTimeout(timer)
      signal.removeEventListener('abort', done)
      resolve()
    }
    signal.addEventListener('abort', done, { once: true })
  })
}

export async function watchKernelEvents(
  client: StreamingApiClient,
  options: KernelEventStreamOptions,
): Promise<void> {
  const delays = options.reconnectDelays?.length ? options.reconnectDelays : [1_000, 2_000, 5_000]
  let reconnect = 0

  while (!options.signal.aborted) {
    try {
      const response = await client.stream('/api/v1/kernels/events', {
        headers: { accept: 'text/event-stream' },
        signal: options.signal,
      })
      if (!response.body) throw new Error('Kernel event stream has no body')
      for await (const event of parseServerSentEvents(response.body)) {
        if (options.signal.aborted) return
        const snapshot = snapshotFrom(event)
        if (snapshot) options.onSnapshot(snapshot)
      }
    } catch (error) {
      if (options.signal.aborted) return
      options.onError?.(error)
    }

    if (options.signal.aborted) return
    await wait(delays[Math.min(reconnect, delays.length - 1)], options.signal)
    reconnect += 1
  }
}
