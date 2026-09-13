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
  let skipLineFeed = false
  let event = 'message'
  let data: string[] = []
  let id: string | undefined

  function dispatch(): ServerSentEvent | undefined {
    const value = data.length === 0 ? undefined : { event: event || 'message', data: data.join('\n'), ...(id === undefined ? {} : { id }) }
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
      // CRLF is one delimiter even when split between network chunks; lone CR also ends a line.
      if (skipLineFeed && buffer.length) {
        if (buffer.startsWith('\n')) buffer = buffer.slice(1)
        skipLineFeed = false
      }
      let newline = buffer.search(/[\r\n]/)
      while (newline >= 0) {
        const line = buffer.slice(0, newline)
        const carriageReturn = buffer[newline] === '\r'
        buffer = buffer.slice(newline + 1)
        if (carriageReturn) {
          if (buffer.startsWith('\n')) buffer = buffer.slice(1)
          else if (!buffer.length) skipLineFeed = true
        }
        const parsed = consume(line)
        if (parsed) yield parsed
        newline = buffer.search(/[\r\n]/)
      }
    }
    // Only a blank line commits an event. EOF must discard the unconfirmed tail.

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
