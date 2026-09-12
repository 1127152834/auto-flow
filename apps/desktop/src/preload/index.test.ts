import { EventEmitter } from 'node:events'
import { beforeEach, expect, it, vi } from 'vitest'
import type { AutomationStudioBridge } from '../shared/automation-studio'
import type { RuntimeBridge } from '../shared/runtime'

let ipc: EventEmitter & { invoke: ReturnType<typeof vi.fn> }
let bridge: AutomationStudioBridge & RuntimeBridge

beforeEach(async () => {
  vi.resetModules()
  ipc = Object.assign(new EventEmitter(), { invoke: vi.fn(async () => undefined) })
  vi.doMock('electron', () => ({ ipcRenderer: ipc, contextBridge: { exposeInMainWorld: (_name: string, value: typeof bridge) => { bridge = value } } }))
  await import('./index')
})

it('freezes the Studio renderer before acknowledging an approved save', async () => {
  const order: string[] = []
  const stopTransition = bridge.onStudioTransition(locked => { if (locked) order.push('locked') })
  const stopLeave = bridge.onPrepareStudioLeave(async reason => { expect(reason).toBe('workspace'); order.push('saved'); return true })
  ipc.invoke.mockImplementation(async (name: string) => { if (name === 'autoflow:studio-leave-result') order.push('reply') })
  await ipc.listeners('autoflow:studio-prepare-leave')[0]!({}, { id: 'leave-1', reason: 'workspace' })
  expect(order).toEqual(['saved', 'locked', 'reply'])
  expect(ipc.invoke).toHaveBeenCalledWith('autoflow:studio-leave-result', 'leave-1', true)
  stopLeave(); stopTransition()
})

it('rejects leave when saving throws or the renderer handler has unmounted', async () => {
  const stop = bridge.onPrepareStudioLeave(async () => { throw new Error('disk full') })
  await ipc.listeners('autoflow:studio-prepare-leave')[0]!({}, { id: 'failed', reason: 'close' })
  expect(ipc.invoke).toHaveBeenCalledWith('autoflow:studio-leave-result', 'failed', false)
  stop()
  await ipc.listeners('autoflow:studio-prepare-leave')[0]!({}, { id: 'unmounted', reason: 'quit' })
  expect(ipc.invoke).toHaveBeenCalledWith('autoflow:studio-leave-result', 'unmounted', false)
})

it('exposes runtime notifications with a removable listener and synchronizes preferences', () => {
  const listener = vi.fn()
  const unsubscribe = bridge.onRuntimeContextChanged(listener)
  const context = { workspaceKey: '/workspace', sidecar: { state: 'stopped' }, preferences: { motion: 'reduce', zoom: 100 }, operation: 'idle' }
  ipc.emit('autoflow:runtime-context-changed', {}, context)
  expect(listener).toHaveBeenCalledWith(context)
  unsubscribe()
  ipc.emit('autoflow:runtime-context-changed', {}, context)
  expect(listener).toHaveBeenCalledOnce()
  ipc.emit('autoflow:preferences-changed', {}, { motion: 'reduce', zoom: 100 })
  expect(document.documentElement.dataset.motion).toBe('reduce')
})
