import '@testing-library/jest-dom/vitest'
import { cleanup, render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { DevicePreview } from '../components/DevicePreview'
import { makeDevice } from './management-fixtures'
import type { AndroidApi } from '../api'

vi.mock('../../../app/ApiProvider', () => ({ useApi: () => ({ instanceId: 'preview-test' }) }))
afterEach(cleanup)

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
