import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
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

it('shows recovery action when the API is unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => {
    throw new TypeError('network error')
  }))

  render(<App />)

  expect(await screen.findByRole('button', { name: '重新连接' })).toBeInTheDocument()
})
