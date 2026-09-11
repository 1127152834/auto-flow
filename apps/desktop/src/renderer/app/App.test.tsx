import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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
      status: 'ok',
      apiVersion: 'v1',
      instanceId: 'test',
    }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    })),
  )

  render(<App />)

  expect(await screen.findByText('服务已连接')).toBeInTheDocument()
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
    status: 'ok',
    apiVersion: 'v1',
    instanceId: 'test',
  }), { status: 200 })))

  render(<App />)

  expect(await screen.findByText('服务已连接')).toBeInTheDocument()
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
    .mockResolvedValueOnce(new Response(JSON.stringify({
      status: 'ok',
      apiVersion: 'v1',
      instanceId: 'test',
    }), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  const button = await screen.findByRole('button', { name: '重新连接' })
  fireEvent.click(button)

  expect(await screen.findByText('服务已连接')).toBeInTheDocument()
  expect(window.autoflow.restartSidecar).toHaveBeenCalledOnce()
  expect(fetchMock).toHaveBeenCalledTimes(2)
})
