import { describe, expect, it, vi } from 'vitest'
import { applySidecarEvent, initialSidecarStatus, validateSidecarHealth } from './supervisor'

describe('sidecar status transitions', () => {
  it('only exposes a ready status after a valid ready event', () => {
    const starting = applySidecarEvent(initialSidecarStatus(), { type: 'spawned' })
    expect(starting).toEqual({ state: 'starting' })
    expect(applySidecarEvent(starting, { type: 'ready', apiVersion: 'v1', instanceId: 'x', port: 43127, baseUrl: 'http://127.0.0.1:43127', token: 'secret' })).toEqual({ state: 'ready', apiVersion: 'v1', instanceId: 'x', port: 43127, baseUrl: 'http://127.0.0.1:43127', token: 'secret' })
  })
})

describe('sidecar health validation', () => {
  it('requires matching authenticated health metadata', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
      expect(url).toBe('http://127.0.0.1:43127/health')
      expect(init.headers).toEqual({ 'x-autoflow-token': 'secret' })
      return new Response(JSON.stringify({ status: 'ok', apiVersion: 'v1', instanceId: 'x' }), { status: 200 })
    }))
    await expect(validateSidecarHealth(
      'http://127.0.0.1:43127',
      'secret',
      { apiVersion: 'v1', instanceId: 'x', port: 43127 },
    )).resolves.toBeUndefined()
    vi.unstubAllGlobals()
  })

  it('rejects mismatched health metadata', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(
      JSON.stringify({ status: 'ok', apiVersion: 'v1', instanceId: 'other' }),
      { status: 200 },
    )))
    await expect(validateSidecarHealth(
      'http://127.0.0.1:43127',
      'secret',
      { apiVersion: 'v1', instanceId: 'x', port: 43127 },
    )).rejects.toThrow('metadata mismatch')
    vi.unstubAllGlobals()
  })
})
