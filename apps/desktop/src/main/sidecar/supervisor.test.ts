import { describe, expect, it, vi } from 'vitest'
import { EventEmitter } from 'node:events'
import { spawn } from 'node:child_process'
import { applySidecarEvent, initialSidecarStatus, validateSidecarHealth } from './supervisor'

vi.mock('node:child_process', () => ({ spawn: vi.fn() }))

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

describe('sidecar startup cancellation', () => {
  it('does not publish ready when health resolves after stop', async () => {
    const stdout = new EventEmitter()
    const child = Object.assign(new EventEmitter(), {
      stdout,
      pid: 123,
      kill: vi.fn(() => queueMicrotask(() => child.emit('exit', 0))),
    })
    vi.mocked(spawn).mockReturnValue(child as never)

    let resolveHealth!: (response: Response) => void
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => { resolveHealth = resolve })))
    const supervisor = new (await import('./supervisor')).SidecarSupervisor({
      instanceId: 'x',
      timeoutMs: 1000,
    })
    const start = supervisor.start()
    stdout.emit('data', 'AUTOFLOW_READY {"apiVersion":"v1","instanceId":"x","port":43127}\n')
    await Promise.resolve()
    const stopping = supervisor.stop()
    resolveHealth(new Response(JSON.stringify({ status: 'ok', apiVersion: 'v1', instanceId: 'x' }), { status: 200 }))
    await stopping
    await expect(start).rejects.toThrow('sidecar stopped')
    expect(supervisor.getStatus()).toEqual({ state: 'stopped' })
    vi.unstubAllGlobals()
  })
})
