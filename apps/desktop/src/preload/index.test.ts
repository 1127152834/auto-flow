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

it('exposes only the Studio window opener without obsolete editor control channels', async () => {
  await bridge.openAutomationStudio()
  expect(ipc.invoke).toHaveBeenCalledWith('autoflow:open-automation-studio')
  expect(bridge).not.toHaveProperty('onPrepareStudioLeave')
  expect(bridge).not.toHaveProperty('onStudioTransition')
  expect(bridge).not.toHaveProperty('exportWorkflow')
  expect(ipc.eventNames()).not.toContain('autoflow:studio-prepare-leave')
  expect(ipc.eventNames()).not.toContain('autoflow:studio-transition')
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
