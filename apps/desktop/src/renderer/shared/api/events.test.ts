import { afterEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from './client'
import { parseServerSentEvents, watchKernelEvents } from './events'
import type { KernelOperation } from './types'

const encoder = new TextEncoder()

function stream(...chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)))
      controller.close()
    },
  })
}

function operation(state: KernelOperation['state']): KernelOperation {
  return {
    id: 'operation-1',
    edition: 'public',
    requestedVersion: '146.0.1.1',
    resolvedVersion: state === 'completed' ? '146.0.1.1' : null,
    releaseChannel: 'stable',
    state,
    progress: state === 'completed' ? 100 : 25,
    message: null,
    error: null,
  }
}

function response(state: KernelOperation['state']): Response {
  return new Response(stream(
    'event: snapshot\r\n',
    `data: ${JSON.stringify({ type: 'snapshot', operations: [operation(state)] })}\r\n\r\n`,
  ))
}

afterEach(() => {
  vi.useRealTimers()
})

it('parses split CRLF frames, multiline data, and ignores heartbeats', async () => {
  const events = []
  for await (const event of parseServerSentEvents(stream(
    ': heart', 'beat\r\n\r\nevent: snap', 'shot\r\ndata: {"type":"snapshot",\r\n',
    'data: "operations":[]}\r\n\r\n',
  ))) events.push(event)

  expect(events).toEqual([{
    event: 'snapshot',
    data: '{"type":"snapshot",\n"operations":[]}',
  }])
})

it('reconnects after a closed stream and receives the fresh snapshot', async () => {
  const controller = new AbortController()
  const snapshots: KernelOperation['state'][] = []
  const streamMock = vi.fn()
    .mockResolvedValueOnce(response('downloading'))
    .mockResolvedValueOnce(response('completed'))
  const client = { stream: streamMock } as unknown as StreamingApiClient

  await watchKernelEvents(client, {
    signal: controller.signal,
    reconnectDelays: [0],
    onSnapshot(snapshot) {
      snapshots.push(snapshot.operations[0].state)
      if (snapshot.operations[0].state === 'completed') controller.abort()
    },
  })

  expect(snapshots).toEqual(['downloading', 'completed'])
  expect(streamMock).toHaveBeenCalledTimes(2)
})

it('backs off reconnects by one, two, then five seconds', async () => {
  vi.useFakeTimers()
  const controller = new AbortController()
  const streamMock = vi.fn(async () => {
    if (streamMock.mock.calls.length === 4) controller.abort()
    throw new Error('closed')
  })
  const watcher = watchKernelEvents({ stream: streamMock } as unknown as StreamingApiClient, {
    signal: controller.signal,
    onSnapshot: vi.fn(),
  })

  await vi.advanceTimersByTimeAsync(0)
  expect(streamMock).toHaveBeenCalledTimes(1)
  await vi.advanceTimersByTimeAsync(1_000)
  expect(streamMock).toHaveBeenCalledTimes(2)
  await vi.advanceTimersByTimeAsync(2_000)
  expect(streamMock).toHaveBeenCalledTimes(3)
  await vi.advanceTimersByTimeAsync(5_000)
  await watcher
  expect(streamMock).toHaveBeenCalledTimes(4)
})
