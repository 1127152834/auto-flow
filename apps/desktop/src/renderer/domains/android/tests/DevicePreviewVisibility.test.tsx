import '@testing-library/jest-dom/vitest'
import { cleanup, render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { DevicePreview } from '../components/DevicePreview'
import { makeDevice } from './management-fixtures'
import type { AndroidApi } from '../api'

vi.mock('../../../app/ApiProvider', () => ({ useApi: () => ({ instanceId: 'preview-test' }) }))
afterEach(() => {
  cleanup()
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
  vi.useRealTimers()
})

function renderPreview(overrides: Parameters<typeof makeDevice>[0] = {}, enabled = true) {
  const preview = vi.fn(async () => new Blob(['png'], { type: 'image/png' }))
  const api = { preview } as unknown as AndroidApi
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><DevicePreview device={makeDevice(overrides)} api={api} enabled={enabled} /></QueryClientProvider>)
  return preview
}

it('does not request a preview while the management snapshot is stale or gated', async () => {
  const stale = renderPreview({}, false)
  await waitFor(() => expect(stale).not.toHaveBeenCalled())
  cleanup()
  const unknown = renderPreview({ androidStatus: 'unknown' })
  await waitFor(() => expect(unknown).not.toHaveBeenCalled())
})

it('does not request a preview for non-ready or controlled devices', async () => {
  const stopped = renderPreview({ androidStatus: 'stopped' })
  await waitFor(() => expect(stopped).not.toHaveBeenCalled())
  cleanup()
  const controlled = renderPreview({ control: 'managing' })
  await waitFor(() => expect(controlled).not.toHaveBeenCalled())
})

it('requests a preview for a ready idle device', async () => {
  const preview = renderPreview()
  await waitFor(() => expect(preview).toHaveBeenCalledWith('11111111-1111-4111-8111-111111111111', expect.any(AbortSignal)))
})

it('refreshes no more often than every five seconds and pauses while hidden', async () => {
  vi.useFakeTimers()
  const preview = vi.fn(async () => new Blob(['png'], { type: 'image/png' }))
  const api = { preview } as unknown as AndroidApi
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><DevicePreview device={makeDevice()} api={api} /></QueryClientProvider>)
  await vi.advanceTimersByTimeAsync(0)
  await Promise.resolve()
  expect(preview).toHaveBeenCalled()
  preview.mockClear()
  await vi.advanceTimersByTimeAsync(4999)
  expect(preview).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(1)
  await vi.waitFor(() => expect(preview).toHaveBeenCalledTimes(1))
  preview.mockClear()
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
  document.dispatchEvent(new Event('visibilitychange'))
  await vi.advanceTimersByTimeAsync(10000)
  expect(preview).not.toHaveBeenCalled()
  vi.useRealTimers()
})

it('limits concurrent preview streams to two and keys a new revision separately', async () => {
  let resolveFirst!: (blob: Blob) => void
  let resolveSecond!: (blob: Blob) => void
  const preview = vi.fn()
    .mockImplementationOnce(() => new Promise<Blob>((resolve) => { resolveFirst = resolve }))
    .mockImplementationOnce(() => new Promise<Blob>((resolve) => { resolveSecond = resolve }))
    .mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
  const api = { preview } as unknown as AndroidApi
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const first = makeDevice({ deviceId: 'preview-1' })
  const second = makeDevice({ deviceId: 'preview-2' })
  const third = makeDevice({ deviceId: 'preview-3' })
  const view = render(<QueryClientProvider client={client}><><DevicePreview device={first} api={api} revision={1} /><DevicePreview device={second} api={api} revision={1} /><DevicePreview device={third} api={api} revision={1} /></></QueryClientProvider>)
  await vi.waitFor(() => expect(preview).toHaveBeenCalledTimes(2))
  resolveFirst(new Blob(['one'], { type: 'image/png' }))
  await vi.waitFor(() => expect(preview).toHaveBeenCalledTimes(3))
  resolveSecond(new Blob(['two'], { type: 'image/png' }))
  view.rerender(<QueryClientProvider client={client}><DevicePreview device={first} api={api} revision={2} /></QueryClientProvider>)
  await vi.waitFor(() => expect(preview).toHaveBeenCalledWith('preview-1', expect.any(AbortSignal)))
})
