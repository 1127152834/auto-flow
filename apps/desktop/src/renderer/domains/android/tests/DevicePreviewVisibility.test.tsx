import '@testing-library/jest-dom/vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { DevicePreview } from '../components/DevicePreview'
import { makeDevice } from './management-fixtures'
import type { AndroidApi } from '../api'

const apiContext = vi.hoisted(() => ({ instanceId: 'preview-test' }))
vi.mock('../../../app/ApiProvider', () => ({ useApi: () => apiContext }))
afterEach(() => {
  cleanup()
  apiContext.instanceId = 'preview-test'
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
  vi.useRealTimers()
  vi.unstubAllGlobals()
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
  vi.unstubAllGlobals()
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


it('waits for the first viewport observation before requesting a screenshot', async () => {
  let observe!: IntersectionObserverCallback
  vi.stubGlobal('IntersectionObserver', class {
    constructor(callback: IntersectionObserverCallback) { observe = callback }
    observe() {}
    disconnect() {}
  })
  const preview = renderPreview()
  await act(async () => { await Promise.resolve() })
  expect(preview).not.toHaveBeenCalled()
  act(() => observe([{ isIntersecting: false }] as IntersectionObserverEntry[], {} as IntersectionObserver))
  expect(preview).not.toHaveBeenCalled()
  act(() => observe([{ isIntersecting: true }] as IntersectionObserverEntry[], {} as IntersectionObserver))
  await waitFor(() => expect(preview).toHaveBeenCalledTimes(1))
})

it('cancels an active preview when its management gate closes', async () => {
  let signal!: AbortSignal
  const preview = vi.fn((_id: string, current: AbortSignal) => new Promise<Blob>((_resolve, reject) => {
    signal = current
    current.addEventListener('abort', () => reject(current.reason), { once: true })
  }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const api = { preview } as unknown as AndroidApi
  const view = render(<QueryClientProvider client={client}><DevicePreview device={makeDevice()} api={api} /></QueryClientProvider>)
  await waitFor(() => expect(preview).toHaveBeenCalledTimes(1))
  view.rerender(<QueryClientProvider client={client}><DevicePreview device={makeDevice()} api={api} enabled={false} /></QueryClientProvider>)
  await waitFor(() => expect(signal.aborted).toBe(true))
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
})

it('does not publish a late screenshot from a cancelled preview after it becomes visible again', async () => {
  let finishOld!: (blob: Blob) => void
  let finishNew!: (blob: Blob) => void
  const preview = vi.fn()
    .mockImplementationOnce(() => new Promise<Blob>((resolve) => { finishOld = resolve }))
    .mockImplementationOnce(() => new Promise<Blob>((resolve) => { finishNew = resolve }))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const api = { preview } as unknown as AndroidApi
  const renderDevice = (enabled: boolean) => <QueryClientProvider client={client}><DevicePreview device={makeDevice()} api={api} enabled={enabled} /></QueryClientProvider>
  const view = render(renderDevice(true))
  await waitFor(() => expect(preview).toHaveBeenCalledTimes(1))
  view.rerender(renderDevice(false))
  view.rerender(renderDevice(true))
  await act(async () => { finishOld(new Blob(['old'])); await Promise.resolve() })
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  await waitFor(() => expect(preview).toHaveBeenCalledTimes(2))
  await act(async () => { finishNew(new Blob(['new'])); await Promise.resolve() })
  await screen.findByRole('img')
})

it('keeps a shared preview alive until its last visible consumer leaves', async () => {
  let signal!: AbortSignal
  const preview = vi.fn((_id: string, current: AbortSignal) => new Promise<Blob>((_resolve, reject) => {
    signal = current
    current.addEventListener('abort', () => reject(current.reason), { once: true })
  }))
  const api = { preview } as unknown as AndroidApi
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const pair = (first: boolean, second: boolean) => <QueryClientProvider client={client}><DevicePreview device={makeDevice()} api={api} enabled={first} /><DevicePreview device={makeDevice()} api={api} enabled={second} /></QueryClientProvider>
  const view = render(pair(true, true))
  await waitFor(() => expect(preview).toHaveBeenCalledTimes(1))
  view.rerender(pair(false, true))
  expect(signal.aborted).toBe(false)
  view.rerender(pair(false, false))
  await waitFor(() => expect(signal.aborted).toBe(true))
})


it('discards a late preview from the previous backend instance', async () => {
  let finishOld!: (blob: Blob) => void
  let finishNew!: (blob: Blob) => void
  const preview = vi.fn()
    .mockImplementationOnce(() => new Promise<Blob>((resolve) => { finishOld = resolve }))
    .mockImplementationOnce(() => new Promise<Blob>((resolve) => { finishNew = resolve }))
  const api = { preview } as unknown as AndroidApi
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const content = () => <QueryClientProvider client={client}><DevicePreview device={makeDevice()} api={api} /></QueryClientProvider>
  const view = render(content())
  await waitFor(() => expect(preview).toHaveBeenCalledTimes(1))
  apiContext.instanceId = 'another-workspace-backend'
  view.rerender(content())
  await waitFor(() => expect(preview).toHaveBeenCalledTimes(2))
  await act(async () => { finishOld(new Blob(['old'])); await Promise.resolve() })
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  await act(async () => { finishNew(new Blob(['new'])); await Promise.resolve() })
  await screen.findByRole('img')
})

it('releases the displayed object URL when the preview is hidden', async () => {
  const revoke = vi.spyOn(URL, 'revokeObjectURL')
  try {
    const preview = vi.fn(async () => new Blob(['png']))
    const api = { preview } as unknown as AndroidApi
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const view = render(<QueryClientProvider client={client}><DevicePreview device={makeDevice()} api={api} /></QueryClientProvider>)
    const source = (await screen.findByRole('img')).getAttribute('src')!
    view.rerender(<QueryClientProvider client={client}><DevicePreview device={makeDevice()} api={api} enabled={false} /></QueryClientProvider>)
    expect(revoke).toHaveBeenCalledWith(source)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  } finally { revoke.mockRestore() }
})
