// @vitest-environment node
import { describe, expect, it, vi } from 'vitest'
import { EventEmitter } from 'node:events'
import { spawn } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { applySidecarEvent, initialSidecarStatus, validateSidecarHealth } from './supervisor'

vi.mock('node:child_process', () => ({ spawn: vi.fn() }))
// The supervisor keeps the sidecar's own output under the data directory; the
// unit test must not create that directory on the machine running the tests.
vi.mock('node:fs', async importOriginal => {
  const actual = await importOriginal<typeof import('node:fs')>()
  return { ...actual, mkdirSync: vi.fn(), createWriteStream: vi.fn() }
})

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

describe('sidecar startup paths', () => {
  it('uses an explicit development module for an isolated QA sidecar', async () => {
    vi.mocked(spawn).mockReset()
    const stdout = new EventEmitter()
    const child = Object.assign(new EventEmitter(), {
      stdout,
      pid: 123,
      kill: vi.fn(),
    })
    vi.mocked(spawn).mockReturnValue(child as never)
    vi.stubGlobal('fetch', vi.fn(async () => new Response(
      JSON.stringify({ status: 'ok', apiVersion: 'v1', instanceId: 'x' }),
      { status: 200 },
    )))

    const supervisor = new (await import('./supervisor')).SidecarSupervisor({
      instanceId: 'x',
      dataDir: '/tmp/autoflow-pm4-qa',
      backendDirectory: '/backend',
      developmentModule: 'tests.qa.pm4_sidecar',
      timeoutMs: 1000,
    })
    const start = supervisor.start()
    stdout.emit('data', 'AUTOFLOW_READY {"apiVersion":"v1","instanceId":"x","port":43127}\n')

    await expect(start).resolves.toMatchObject({ state: 'ready' })
    expect(spawn).toHaveBeenCalledWith(
      'uv',
      ['run', '--directory', '/backend', 'python', '-m', 'tests.qa.pm4_sidecar', '--port', '0', '--instance-id', 'x', '--parent-pid', String(process.pid), '--data-dir', '/tmp/autoflow-pm4-qa'],
      expect.anything(),
    )
    // The local service's own output has to be readable after a failed start.
    expect(vi.mocked(mkdirSync)).toHaveBeenCalledWith('/tmp/autoflow-pm4-qa/logs', { recursive: true })
    vi.unstubAllGlobals()
  })

  it('passes the injected data directory through args and environment', async () => {
    vi.mocked(spawn).mockReset()
    const stdout = new EventEmitter()
    const child = Object.assign(new EventEmitter(), {
      stdout,
      pid: 123,
      kill: vi.fn(),
    })
    vi.mocked(spawn).mockReturnValue(child as never)
    vi.stubGlobal('fetch', vi.fn(async () => new Response(
      JSON.stringify({ status: 'ok', apiVersion: 'v1', instanceId: 'x' }),
      { status: 200 },
    )))

    const supervisor = new (await import('./supervisor')).SidecarSupervisor({
      instanceId: 'x',
      dataDir: '/tmp/autoflow-test',
      backendDirectory: '/backend',
      timeoutMs: 1000,
    })
    const start = supervisor.start()
    stdout.emit('data', 'AUTOFLOW_READY {"apiVersion":"v1","instanceId":"x","port":43127}\n')

    await expect(start).resolves.toMatchObject({ state: 'ready' })
    const spawnedOptions = vi.mocked(spawn).mock.calls[0][2] as { env: NodeJS.ProcessEnv }
    const hostToken = spawnedOptions.env.AUTOFLOW_HOST_TOKEN
    expect(hostToken).toMatch(/^[0-9a-f]{64}$/)
    expect(hostToken).not.toBe(spawnedOptions.env.AUTOFLOW_INSTANCE_TOKEN)
    expect(JSON.stringify(supervisor.getStatus())).not.toContain(hostToken)
    expect(supervisor.getHostStatus()).toEqual({ state: 'ready', baseUrl: 'http://127.0.0.1:43127', hostToken, dataDir: '/tmp/autoflow-test' })
    expect(spawn).toHaveBeenCalledWith(
      'uv',
      ['run', '--directory', '/backend', 'python', '-m', 'autoflow', '--port', '0', '--instance-id', 'x', '--parent-pid', String(process.pid), '--data-dir', '/tmp/autoflow-test'],
      expect.objectContaining({
        env: expect.objectContaining({
          AUTOFLOW_DATA_DIR: '/tmp/autoflow-test',
        }),
      }),
    )
    vi.unstubAllGlobals()
  })
})

describe('sidecar startup cancellation', () => {
  it('does not publish ready when health resolves after stop', async () => {
    vi.mocked(spawn).mockReset()
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
      dataDir: '/tmp/autoflow-test',
      backendDirectory: '/backend',
      timeoutMs: 1000,
    })
    const start = supervisor.start()
    stdout.emit('data', 'AUTOFLOW_READY {"apiVersion":"v1","instanceId":"x","port":43127}\n')
    await Promise.resolve()
    const stopping = supervisor.stop()
    resolveHealth(new Response(JSON.stringify({ status: 'ok', apiVersion: 'v1', instanceId: 'x' }), { status: 200 }))
    await stopping
    expect(supervisor.getHostStatus()).toEqual({ state: 'stopped' })
    await expect(start).rejects.toThrow('sidecar stopped')
    expect(supervisor.getStatus()).toEqual({ state: 'stopped' })
    vi.unstubAllGlobals()
  })
})

describe('cooperative sidecar shutdown', () => {
  it.each(['darwin', 'win32'])('uses the host-only shutdown request before the bounded kill on %s', async platform => {
    vi.resetModules()
    vi.doMock('node:process', () => ({ platform }))
    vi.useFakeTimers()
    const stdout = new EventEmitter()
    const child = Object.assign(new EventEmitter(), {
      stdout, pid: 123, exitCode: null, signalCode: null, kill: vi.fn(),
    })
    vi.mocked(spawn).mockReset().mockReturnValue(child as never)
    const fetchMock = vi.fn(async (url: string) => {
      // Windows must preserve the budget even if the shutdown response is lost.
      if (platform === 'win32' && url.endsWith('/shutdown')) throw new TypeError('response lost')
      return new Response(JSON.stringify(
        url.endsWith('/health') ? { status: 'ok', apiVersion: 'v1', instanceId: 'x' } : { stopping: true },
      ), { status: 200 })
    })
    vi.stubGlobal('fetch', fetchMock)
    try {
      const { SidecarSupervisor } = await import('./supervisor')
      const supervisor = new SidecarSupervisor({ instanceId: 'x', dataDir: '/tmp/shutdown', backendDirectory: '/backend' })
      const starting = supervisor.start()
      stdout.emit('data', 'AUTOFLOW_READY {"apiVersion":"v1","instanceId":"x","port":43127}\n')
      await starting
      const host = supervisor.getHostStatus()
      expect(host.state).toBe('ready')
      const stopping = supervisor.stop()
      expect(fetchMock).toHaveBeenLastCalledWith('http://127.0.0.1:43127/internal/lifecycle/shutdown', expect.objectContaining({
        method: 'POST', headers: { 'x-autoflow-host-token': host.state === 'ready' ? host.hostToken : '' },
        signal: expect.any(AbortSignal),
      }))
      expect(supervisor.getHostStatus()).toEqual({ state: 'stopped' })
      await vi.advanceTimersByTimeAsync(9000)
      expect(child.kill).not.toHaveBeenCalled()
      await vi.advanceTimersByTimeAsync(1000)
      await stopping
      if (platform === 'win32') expect(spawn).toHaveBeenLastCalledWith('taskkill', ['/pid', '123', '/t', '/f'])
      else expect(child.kill).toHaveBeenCalledWith('SIGKILL')
      expect(supervisor.getStatus()).toEqual({ state: 'stopped' })
    } finally {
      vi.useRealTimers(); vi.unstubAllGlobals(); vi.doUnmock('node:process'); vi.resetModules()
    }
  })

  it('finishes immediately when the cooperative process exits', async () => {
    const stdout = new EventEmitter()
    const child = Object.assign(new EventEmitter(), { stdout, pid: 123, exitCode: null, signalCode: null, kill: vi.fn() })
    vi.mocked(spawn).mockReset().mockReturnValue(child as never)
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.endsWith('/shutdown')) queueMicrotask(() => child.emit('exit', 0))
      return new Response(JSON.stringify({ status: 'ok', apiVersion: 'v1', instanceId: 'x' }), { status: 200 })
    }))
    try {
      const { SidecarSupervisor } = await import('./supervisor')
      const supervisor = new SidecarSupervisor({ instanceId: 'x', dataDir: '/tmp/shutdown', backendDirectory: '/backend' })
      const starting = supervisor.start()
      stdout.emit('data', 'AUTOFLOW_READY {"apiVersion":"v1","instanceId":"x","port":43127}\n')
      await starting
      await supervisor.stop()
      expect(child.kill).not.toHaveBeenCalled()
      expect(supervisor.getStatus()).toEqual({ state: 'stopped' })
    } finally { vi.unstubAllGlobals() }
  })
})
