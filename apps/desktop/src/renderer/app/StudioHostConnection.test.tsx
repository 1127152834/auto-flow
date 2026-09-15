import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { DesktopRuntimeContext } from '../../shared/runtime'
import { getBackendBaseUrl } from '../domains/workflows/api/config'
import { studioFetch } from '../domains/workflows/api/transport'
import { StudioHostConnection } from './StudioHostConnection'

let changed: ((runtime: DesktopRuntimeContext) => void) | undefined

const runtime = (instanceId: string, port: number): DesktopRuntimeContext => ({
  workspaceKey: '/tmp/autoflow-studio-host',
  sidecar: {
    state: 'ready',
    apiVersion: 'v1',
    port,
    baseUrl: `http://127.0.0.1:${port}`,
    token: `token-${instanceId}`,
    instanceId,
  },
  preferences: { zoom: 100, motion: 'system' },
  operation: 'idle',
})

afterEach(() => {
  cleanup()
  changed = undefined
  vi.unstubAllGlobals()
})

it('binds Studio requests to the current authenticated host runtime and replaces it without replay', async () => {
  let current = runtime('one', 43127)
  const requests: Array<{ url: string; token: string | null }> = []
  vi.stubGlobal('autoflow', {
    getRuntimeContext: vi.fn(async () => current),
    onRuntimeContextChanged: vi.fn((listener: typeof changed) => { changed = listener; return vi.fn() }),
    restartSidecar: vi.fn(),
  })
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new Request(input, init)
    requests.push({ url: request.url, token: request.headers.get('x-autoflow-token') })
    if (new URL(request.url).pathname === '/health') {
      return Response.json({ status: 'ok', apiVersion: 'v1', instanceId: current.sidecar.state === 'ready' ? current.sidecar.instanceId : '' })
    }
    return Response.json({ items: [] })
  }))

  render(<StudioHostConnection><button onClick={() => void studioFetch(`${getBackendBaseUrl()}/api/workflows`)}>读取流程</button></StudioHostConnection>)
  await screen.findByRole('button', { name: '读取流程' })
  fireEvent.click(screen.getByRole('button', { name: '读取流程' }))
  await waitFor(() => expect(requests.some(item => item.url === 'http://127.0.0.1:43127/api/workflows' && item.token === 'token-one')).toBe(true))

  current = runtime('two', 43128)
  await act(async () => { changed?.(current) })
  await screen.findByRole('button', { name: '读取流程' })
  fireEvent.click(screen.getByRole('button', { name: '读取流程' }))
  await waitFor(() => expect(requests.some(item => item.url === 'http://127.0.0.1:43128/api/workflows' && item.token === 'token-two')).toBe(true))
  expect(requests.filter(item => new URL(item.url).pathname === '/api/workflows')).toHaveLength(2)
})
