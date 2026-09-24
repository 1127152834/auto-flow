// @vitest-environment node
import { afterEach, expect, it, vi } from 'vitest'
import type { SidecarStatus } from '../shared/runtime'
import { ScheduledHotkeyController, toElectronAccelerator } from './scheduled-hotkeys'

afterEach(() => vi.useRealTimers())

it('maps recorded WebRPA keys to Electron accelerators', () => {
  expect(toElectronAccelerator('ctrl+shift+k')).toBe('Control+Shift+K')
  expect(toElectronAccelerator('cmd+alt+f12')).toBe('Command+Alt+F12')
  expect(toElectronAccelerator('ctrl+shift')).toBeNull()
})

it('registers host shortcuts and retries a lost trigger response with one command id', async () => {
  let status: SidecarStatus = { state: 'ready', apiVersion: 'v1', instanceId: 'one', port: 1, baseUrl: 'http://local', token: 'token' }
  const callbacks = new Map<string, () => void>()
  const unregister = vi.fn((key: string) => callbacks.delete(key))
  const requests: Array<{ url: string; init?: RequestInit }> = []
  let triggerAttempts = 0
  const request = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    requests.push({ url, init })
    if (url.endsWith('/registrations')) return new Response(JSON.stringify([{ task_id: 'task-1', hotkey: 'ctrl+shift+k' }]), { status: 200 })
    triggerAttempts += 1
    if (triggerAttempts === 1) throw new TypeError('response lost')
    return new Response(JSON.stringify({ status: 'queued' }), { status: 202 })
  }) as typeof fetch
  const controller = new ScheduledHotkeyController({
    shortcuts: { register: (key, callback) => { callbacks.set(key, callback); return true }, unregister },
    getSidecarStatus: () => status,
    request,
  })

  await controller.reconcile()
  expect([...callbacks]).toHaveLength(1)
  callbacks.get('Control+Shift+K')!()
  await vi.waitFor(() => expect(triggerAttempts).toBe(2))
  const triggerRequests = requests.filter(item => item.url.includes('/trigger'))
  expect(triggerRequests[0]!.init?.headers).toEqual(triggerRequests[1]!.init?.headers)

  status = { state: 'starting' }
  await controller.reconcile()
  expect(unregister).toHaveBeenCalledWith('Control+Shift+K')
  expect(callbacks.size).toBe(0)
})

it('fences callbacks to the sidecar instance that registered them', async () => {
  let status: SidecarStatus = { state: 'ready', apiVersion: 'v1', instanceId: 'one', port: 1, baseUrl: 'http://one', token: 'one' }
  let callback: (() => void) | undefined
  const request = vi.fn(async (input: string | URL | Request) => String(input).endsWith('/registrations')
    ? new Response(JSON.stringify([{ task_id: 'task-1', hotkey: 'f8' }]), { status: 200 })
    : new Response('{}', { status: 202 })) as typeof fetch
  const controller = new ScheduledHotkeyController({
    shortcuts: { register: (_key, value) => { callback = value; return true }, unregister: vi.fn() },
    getSidecarStatus: () => status,
    request,
  })
  await controller.reconcile()
  status = { state: 'ready', apiVersion: 'v1', instanceId: 'two', port: 2, baseUrl: 'http://two', token: 'two' }
  callback!()
  await Promise.resolve()
  expect(request).toHaveBeenCalledTimes(1)
})
