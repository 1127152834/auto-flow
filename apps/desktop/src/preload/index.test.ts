import { EventEmitter } from 'node:events'
import { beforeEach, expect, it, vi } from 'vitest'
import type { AutomationStudioBridge } from '../shared/automation-studio'
import type { ExternalLinkBridge } from '../shared/external-links'
import type { GoogleSheetsBridge } from '../shared/google-sheets'
import type { ProjectFileBridge } from '../shared/project-files'
import type { RuntimeBridge } from '../shared/runtime'

let ipc: EventEmitter & { invoke: ReturnType<typeof vi.fn> }
let bridge: AutomationStudioBridge & RuntimeBridge & ProjectFileBridge & ExternalLinkBridge & GoogleSheetsBridge

beforeEach(async () => {
  vi.resetModules()
  ipc = Object.assign(new EventEmitter(), { invoke: vi.fn(async () => undefined) })
  vi.doMock('electron', () => ({ ipcRenderer: ipc, contextBridge: { exposeInMainWorld: (_name: string, value: typeof bridge) => { bridge = value } } }))
  await import('./index')
})

it('exposes the controlled Studio leave subscription without arbitrary editor access', async () => {
  await bridge.openAutomationStudio()
  expect(ipc.invoke).toHaveBeenCalledWith('autoflow:open-automation-studio')
  expect(bridge.onPrepareStudioLeave).toBeTypeOf('function')
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


it('exposes controlled project file choices and per-window proof without paths', async () => {
  await bridge.chooseExcelInput('project')
  await bridge.chooseXlsxOutput('project', '资料.xlsx')
  await bridge.getProjectFileContext()
  expect(ipc.invoke).toHaveBeenCalledWith('autoflow:project-files:choose-excel-input', 'project')
  expect(ipc.invoke).toHaveBeenCalledWith('autoflow:project-files:choose-xlsx-output', 'project', '资料.xlsx')
  expect(ipc.invoke).toHaveBeenCalledWith('autoflow:project-files:context')
})

it('forwards the Google Sheets handshake without exposing a credential path', async () => {
  await bridge.connectGoogleSheets('project', '运营账号')
  expect(ipc.invoke).toHaveBeenCalledWith('autoflow:google-sheets:connect', 'project', '运营账号')
  expect(bridge).not.toHaveProperty('googleCredentials')
  expect(bridge).not.toHaveProperty('readConfigFile')
})

it('exposes only the named external link invocation', async () => {
  await bridge.openExternalLink('https://example.com')
  expect(ipc.invoke).toHaveBeenCalledWith('autoflow:open-external-link', 'https://example.com')
  expect(bridge).not.toHaveProperty('ipcRenderer')
  expect(bridge).not.toHaveProperty('shell')
})

it('forwards only the result of the registered leave handler and unsubscribes',async()=>{
 const handler=vi.fn(async()=>false)
 const unsubscribe=bridge.onPrepareStudioLeave(handler)
 expect(ipc.invoke).toHaveBeenCalledWith('autoflow:studio-leave-ready')
 ipc.emit('autoflow:studio-prepare-leave',{}, {id:'close-1',reason:'quit'})
 await Promise.resolve();await Promise.resolve()
 expect(handler).toHaveBeenCalledWith({id:'close-1',reason:'quit'})
 expect(ipc.invoke).toHaveBeenCalledWith('autoflow:studio-leave-result',{id:'close-1',allowed:false})
 unsubscribe();expect(ipc.listenerCount('autoflow:studio-prepare-leave')).toBe(0)
})
