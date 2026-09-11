import { QueryClient, useQueryClient } from '@tanstack/react-query'
import { act, render, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiProvider } from '../../app/ApiProvider'
import type { KernelOperation } from '../../shared/api/types'
import { kernelKeys, mergeKernelOperation, mergeKernelOperationSnapshot, useKernelEvents } from './hooks'

const encoder = new TextEncoder()

function operation(state: KernelOperation['state']): KernelOperation {
  return {
    id: 'operation-1', edition: 'public', requestedVersion: '146.0.1.1',
    resolvedVersion: state === 'completed' ? '146.0.1.1' : null,
    releaseChannel: 'stable', state, progress: null, message: null, error: null,
  }
}

function frame(state: KernelOperation['state']): Uint8Array {
  return encoder.encode(`event: snapshot\ndata: ${JSON.stringify({
    type: 'snapshot', operations: [operation(state)],
  })}\n\n`)
}

function Harness({
  onClient,
  onTerminal,
}: {
  onClient(client: QueryClient): void
  onTerminal?(operation: KernelOperation): void
}) {
  const queryClient = useQueryClient()
  useKernelEvents({ onTerminal })
  useEffect(() => { onClient(queryClient) }, [onClient, queryClient])
  return null
}

afterEach(() => vi.unstubAllGlobals())

it('does not move an operation backward after a terminal or cancelling state', () => {
  expect(mergeKernelOperation(operation('completed'), operation('queued')).state).toBe('completed')
  expect(mergeKernelOperation(operation('cancelling'), operation('extracting')).state).toBe('cancelling')
  expect(mergeKernelOperation(operation('downloading'), operation('verifying')).state).toBe('verifying')
})

it('appends cached-only operations after an older snapshot', () => {
  const old = { ...operation('failed'), id: 'operation-old' }
  const newer = { ...operation('queued'), id: 'operation-new' }
  expect(mergeKernelOperationSnapshot([newer], [old])).toEqual([old, newer])
})

it('drops late events from an old sidecar instance', async () => {
  const streams = new Map<string, ReadableStreamDefaultController<Uint8Array>>()
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    return new Response(new ReadableStream({
      start(controller) { streams.set(url, controller) },
    }))
  }))
  const clients: QueryClient[] = []
  const onClient = (client: QueryClient) => { if (!clients.includes(client)) clients.push(client) }
  const view = render(
    <ApiProvider baseUrl="http://127.0.0.1:1" token="old" instanceId="old-instance">
      <Harness onClient={onClient} />
    </ApiProvider>,
  )
  await waitFor(() => expect(streams.has('http://127.0.0.1:1/api/v1/kernels/events')).toBe(true))

  view.rerender(
    <ApiProvider baseUrl="http://127.0.0.1:2" token="new" instanceId="new-instance">
      <Harness onClient={onClient} />
    </ApiProvider>,
  )
  await waitFor(() => expect(streams.has('http://127.0.0.1:2/api/v1/kernels/events')).toBe(true))
  act(() => {
    streams.get('http://127.0.0.1:1/api/v1/kernels/events')?.enqueue(frame('completed'))
    streams.get('http://127.0.0.1:2/api/v1/kernels/events')?.enqueue(frame('downloading'))
  })

  await waitFor(() => expect(clients[1].getQueryData(kernelKeys.operations('new-instance')))
    .toEqual([operation('downloading')]))
  expect(clients[0].getQueryData(kernelKeys.operations('old-instance'))).toBeUndefined()
  expect(clients[0]).not.toBe(clients[1])
  streams.forEach((controller) => controller.close())
  view.unmount()
})

it('notifies a terminal transition only once across repeated snapshots', async () => {
  let streamController: ReadableStreamDefaultController<Uint8Array> | undefined
  vi.stubGlobal('fetch', vi.fn(async () => new Response(new ReadableStream({
    start(controller) { streamController = controller },
  }))))
  const onTerminal = vi.fn()
  const clients: QueryClient[] = []
  const view = render(
    <ApiProvider baseUrl="http://127.0.0.1:1" token="secret" instanceId="instance-1">
      <Harness onClient={(client) => clients.push(client)} onTerminal={onTerminal} />
    </ApiProvider>,
  )
  await waitFor(() => expect(streamController).toBeDefined())

  act(() => streamController?.enqueue(frame('downloading')))
  await waitFor(() => expect(clients[0].getQueryData(kernelKeys.operations('instance-1')))
    .toEqual([operation('downloading')]))
  act(() => {
    streamController?.enqueue(frame('completed'))
    streamController?.enqueue(frame('completed'))
  })

  await waitFor(() => expect(onTerminal).toHaveBeenCalledTimes(1))
  expect(onTerminal).toHaveBeenCalledWith(operation('completed'))
  streamController?.close()
  view.unmount()
})
