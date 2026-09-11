import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { App } from './App'

beforeEach(() => {
  vi.stubGlobal('autoflow', {
    getSidecarStatus: vi.fn(async () => ({
      state: 'ready',
      apiVersion: 'v1',
      port: 43127,
      baseUrl: 'http://127.0.0.1:43127',
      token: 'test',
      instanceId: 'test',
    })),
    restartSidecar: vi.fn(async () => ({
      state: 'ready',
      apiVersion: 'v1',
      port: 43127,
      baseUrl: 'http://127.0.0.1:43127',
      token: 'test',
      instanceId: 'test',
    })),
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('shows sidecar health after the API responds', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify({
      items: [], total: 0, status: 'ok',
      apiVersion: 'v1',
      instanceId: 'test',
    }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    })),
  )

  render(<App />)

  expect(await screen.findByText('本地服务正常')).toBeInTheDocument()
})

it('waits for a starting sidecar before checking health', async () => {
  vi.mocked(window.autoflow.getSidecarStatus)
    .mockResolvedValueOnce({ state: 'starting' })
    .mockResolvedValueOnce({
      state: 'ready',
      apiVersion: 'v1',
      port: 43127,
      baseUrl: 'http://127.0.0.1:43127',
      token: 'test',
      instanceId: 'test',
    })
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
    items: [], total: 0, status: 'ok',
    apiVersion: 'v1',
    instanceId: 'test',
  }), { status: 200 })))

  render(<App />)

  expect(await screen.findByText('本地服务正常')).toBeInTheDocument()
  expect(window.autoflow.getSidecarStatus).toHaveBeenCalledTimes(2)
})

it('shows recovery action when the API is unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => {
    throw new TypeError('network error')
  }))

  render(<App />)

  expect(await screen.findByRole('button', { name: '重新连接' })).toBeInTheDocument()
})

it('restarts the sidecar and reconnects after the recovery action', async () => {
  const fetchMock = vi.fn()
    .mockRejectedValueOnce(new TypeError('network error'))
    .mockImplementation(async () => new Response(JSON.stringify({
      items: [], total: 0, status: 'ok',
      apiVersion: 'v1',
      instanceId: 'test',
    }), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  const button = await screen.findByRole('button', { name: '重新连接' })
  fireEvent.click(button)

  expect(await screen.findByText('本地服务正常')).toBeInTheDocument()
  expect(window.autoflow.restartSidecar).toHaveBeenCalledOnce()
  expect(fetchMock).toHaveBeenCalledTimes(3)
})

it('reacquires the sidecar once after an auth error and stops repeated recovery', async () => {
  const requests: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    requests.push(url)
    if (url.endsWith('/health')) return Response.json({ status: 'ok', apiVersion: 'v1', instanceId: 'test' })
    return Response.json({ error: { code: 'SIDECAR_UNAUTHORIZED', message: '本地服务认证失效', details: {} } }, { status: 401 })
  }))
  render(<App />)
  expect(await screen.findByRole('button', { name: '重新连接' })).toBeInTheDocument()
  await waitFor(() => expect(window.autoflow.getSidecarStatus).toHaveBeenCalledTimes(2))
  expect(requests.filter(url => url.endsWith('/model-providers'))).toHaveLength(2)
})

it('never replays a model-test POST after reacquiring sidecar credentials', async () => {
  const provider = { id: 'p1', name: 'Local fixture', providerKind: 'custom', baseUrl: 'http://127.0.0.1:1234/v1', presetId: 'custom', apiKeyConfigured: false, enabled: true, description: '', connectionStatus: 'untested', lastCheckedAt: null, lastCheckMessage: null, models: [{ id: 'm1', providerId: 'p1', modelKey: 'test-model', displayName: 'Test Model', tagsJson: [], enabled: true, contextWindow: null, description: '' }] }
  let modelPosts = 0
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/health')) return Response.json({ status: 'ok', apiVersion: 'v1', instanceId: 'test' })
    if (init?.method === 'POST') {
      modelPosts++
      return Response.json({ error: { code: 'SIDECAR_UNAUTHORIZED', message: '本地服务认证失效', details: {} } }, { status: 401 })
    }
    return Response.json({ items: [provider], total: 1 })
  }))
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: 'Test Model 测试模型' }))
  await waitFor(() => expect(window.autoflow.getSidecarStatus).toHaveBeenCalledTimes(2))
  expect(await screen.findByRole('button', { name: 'Test Model 测试模型' })).toBeEnabled()
  expect(modelPosts).toBe(1)
})
