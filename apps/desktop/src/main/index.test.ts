// @vitest-environment node
import { EventEmitter } from 'node:events'
import { afterEach, beforeEach, expect, it, vi, type Mock } from 'vitest'
import type { DesktopIpcEvent } from './ipc/automation-studio'
import type { SettingsControllerOptions } from './settings/controller'
import type { DesktopRuntimeContext } from '../shared/runtime'

class FakeWindow extends EventEmitter {
  static instances: FakeWindow[] = []
  destroyed = false
  webContents = Object.assign(new EventEmitter(), { id: 10 + FakeWindow.instances.length, mainFrame: {}, setWindowOpenHandler: vi.fn(), setZoomFactor: vi.fn(), send: vi.fn() })
  loadURL = vi.fn(async () => {})
  loadFile = vi.fn(async () => {})
  show = vi.fn()
  focus = vi.fn()
  setTitle = vi.fn()
  restore = vi.fn()
  isDestroyed() { return this.destroyed }
  isMinimized() { return false }
  destroy() { this.destroyed = true; this.emit('closed') }
  close() { const event = { preventDefault: vi.fn() }; this.emit('close', event); if (!event.preventDefault.mock.calls.length) this.destroy() }
  constructor() { super(); FakeWindow.instances.push(this) }
}

const runtime = (): DesktopRuntimeContext => ({ workspaceKey: '/workspace-a', sidecar: { state: 'ready', apiVersion: 'v1', baseUrl: 'http://127.0.0.1:43127', token: 'public-token', port: 43127, instanceId: 'instance-a' }, preferences: { zoom: 100, motion: 'system' }, operation: 'idle' })
let context: DesktopRuntimeContext
let handlers: Map<string, (event: DesktopIpcEvent, ...args: unknown[]) => unknown>
let app: EventEmitter & { quit: Mock<() => void> }
let settings: { shutdown: ReturnType<typeof vi.fn>; confirmWorkspace: ReturnType<typeof vi.fn>; restart: ReturnType<typeof vi.fn> }
let reloadMenuItem: { role: string; enabled: boolean }
const sender = (window: FakeWindow) => ({ sender: window.webContents, senderFrame: window.webContents.mainFrame })
const invoke = (channel: string, window: FakeWindow, ...args: unknown[]) => handlers.get(channel)!(sender(window), ...args)
const pendingRequest = (window: FakeWindow) => window.webContents.send.mock.calls.slice().reverse().find(call => call[0] === 'autoflow:studio-prepare-leave')![1] as { id: string; reason: string }

beforeEach(async () => {
  vi.resetModules()
  vi.stubGlobal('__dirname', '/compiled/main')
  FakeWindow.instances = []
  handlers = new Map()
  context = runtime()
  reloadMenuItem = { role: 'reload', enabled: true }
  settings = { shutdown: vi.fn(async () => {}), confirmWorkspace: vi.fn(async () => { context = { ...runtime(), workspaceKey: '/workspace-b' }; return {} }), restart: vi.fn(async () => context.sidecar) }
  app = Object.assign(new EventEmitter(), {
    getPath: () => '/tmp/autoflow-main-test', getVersion: () => '0.1.0', isReady: () => true, isPackaged: false,
    requestSingleInstanceLock: () => true, whenReady: async () => {}, quit: vi.fn(),
  })
  app.quit.mockImplementation(() => {
    const event = { preventDefault: vi.fn() }
    app.emit('before-quit', event)
    if (!event.preventDefault.mock.calls.length) for (const window of FakeWindow.instances) if (!window.destroyed) window.close()
  })
  vi.doMock('electron', () => ({ app, BrowserWindow: FakeWindow, Menu: { getApplicationMenu: () => ({ items: [reloadMenuItem] }) }, ipcMain: { handle: (name: string, handler: (event: DesktopIpcEvent, ...args: unknown[]) => unknown) => handlers.set(name, handler), removeHandler: (name: string) => handlers.delete(name) }, clipboard: {}, shell: { openPath: vi.fn(), showItemInFolder: vi.fn() }, dialog: { showErrorBox: vi.fn() } }))
  vi.doMock('./settings/controller', () => ({ SettingsController: class {
    constructor(private options: SettingsControllerOptions) {}
    start = async () => {}
    shutdown = settings.shutdown
    confirmWorkspace = settings.confirmWorkspace
    restart = settings.restart
    getRuntimeContext = () => context
    getPublicStatus = () => context.sidecar
    getPreferences = () => context.preferences
    getHostStatus = () => ({ state: 'stopped' })
    invalidateChoices = vi.fn()
    snapshot = async () => ({ workspace: { path: context.workspaceKey } })
    setPreferences = async () => { this.options.applyPreferences({ zoom: 125, motion: 'reduce' }) }
  } }))
  await import('./index')
  await vi.waitFor(() => expect(FakeWindow.instances).toHaveLength(1))
})
afterEach(() => { vi.unstubAllGlobals(); vi.doUnmock('electron'); vi.doUnmock('./settings/controller') })

async function openStudio() {
  await invoke('autoflow:open-automation-studio', FakeWindow.instances[0]!)
  const studio = FakeWindow.instances[1]!
  invoke('autoflow:studio-ready', studio, true)
  return studio
}

it('grants runtime access to registered main frames but keeps settings and credential mutations main-only', async () => {
  const main = FakeWindow.instances[0]!
  const studio = await openStudio()
  expect(invoke('autoflow:runtime-context', main)).toEqual(context)
  expect(invoke('autoflow:runtime-context', studio)).toEqual(context)
  expect(() => handlers.get('autoflow:runtime-context')!({ ...sender(studio), senderFrame: {} })).toThrow()
  const stranger = new FakeWindow()
  expect(() => invoke('autoflow:runtime-context', stranger)).toThrow()
  await expect(invoke('autoflow:settings:preferences', studio, {})).resolves.toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
  await expect(invoke('autoflow:copy-proxy-credentials', studio, {})).rejects.toThrow()
  await expect(invoke('autoflow:sidecar-restart', studio)).resolves.toEqual(context.sidecar)
  expect(settings.restart).toHaveBeenCalledOnce()
  expect(JSON.stringify(invoke('autoflow:runtime-context', studio))).not.toContain('hostToken')
})

it('does not change workspace before save approval, and publishes new context before unlocking Studio', async () => {
  const studio = await openStudio()
  const change = invoke('autoflow:settings:confirm-workspace', FakeWindow.instances[0]!, 'choice')
  expect(pendingRequest(studio).reason).toBe('workspace')
  expect(settings.confirmWorkspace).not.toHaveBeenCalled()
  invoke('autoflow:studio-leave-result', studio, pendingRequest(studio).id, true)
  await expect(change).resolves.toMatchObject({ ok: true })
  expect(settings.confirmWorkspace).toHaveBeenCalledWith('choice')
  const messages = studio.webContents.send.mock.calls
  expect(messages.at(-2)).toEqual(['autoflow:runtime-context-changed', context])
  expect(messages.at(-1)).toEqual(['autoflow:studio-transition', false])
})

it('cancels a workspace switch on rejected save and unfreezes the old document after switch failure', async () => {
  const studio = await openStudio()
  const main = FakeWindow.instances[0]!
  const cancelled = invoke('autoflow:settings:confirm-workspace', main, 'choice')
  invoke('autoflow:studio-leave-result', studio, pendingRequest(studio).id, false)
  await expect(cancelled).resolves.toMatchObject({ ok: false, error: { code: 'STUDIO_TRANSITION_CANCELLED' } })
  expect(settings.confirmWorkspace).not.toHaveBeenCalled()
  settings.confirmWorkspace.mockRejectedValueOnce(new Error('target failed'))
  const failed = invoke('autoflow:settings:confirm-workspace', main, 'choice')
  invoke('autoflow:studio-leave-result', studio, pendingRequest(studio).id, true)
  await expect(failed).resolves.toMatchObject({ ok: false })
  expect(context.workspaceKey).toBe('/workspace-a')
  expect(studio.webContents.send).toHaveBeenLastCalledWith('autoflow:studio-transition', false)
  expect(studio.destroyed).toBe(false)
})

it('waits for Studio save before stopping the sidecar and honors cancel on application quit', async () => {
  const studio = await openStudio()
  app.quit()
  expect(pendingRequest(studio).reason).toBe('quit')
  expect(settings.shutdown).not.toHaveBeenCalled()
  invoke('autoflow:studio-leave-result', studio, pendingRequest(studio).id, false)
  await Promise.resolve(); await Promise.resolve()
  expect(settings.shutdown).not.toHaveBeenCalled()
  expect(studio.destroyed).toBe(false)
  app.quit()
  invoke('autoflow:studio-leave-result', studio, pendingRequest(studio).id, true)
  await vi.waitFor(() => expect(settings.shutdown).toHaveBeenCalledOnce())
  await vi.waitFor(() => expect(studio.destroyed).toBe(true))
})

it('keeps Studio alive and authorized when the main window closes and is recreated', async () => {
  const studio = await openStudio()
  const original = FakeWindow.instances[0]!
  original.close()
  expect(studio.destroyed).toBe(false)
  expect(invoke('autoflow:runtime-context', studio)).toEqual(context)
  app.emit('activate')
  await vi.waitFor(() => expect(FakeWindow.instances).toHaveLength(3))
  const replacement = FakeWindow.instances[2]!
  await invoke('autoflow:open-automation-studio', replacement)
  expect(FakeWindow.instances).toHaveLength(3)
  expect(() => invoke('autoflow:runtime-context', original)).toThrow()
  await invoke('autoflow:settings:preferences', replacement, {})
  expect(replacement.webContents.setZoomFactor).toHaveBeenCalledWith(1.25)
  expect(studio.webContents.setZoomFactor).toHaveBeenCalledWith(1.25)
})

it('restores the existing reload menu when focus returns from Studio to the main window', async () => {
  const studio = await openStudio()
  studio.emit('focus')
  expect(reloadMenuItem.enabled).toBe(false)
  FakeWindow.instances[0]!.emit('focus')
  expect(reloadMenuItem.enabled).toBe(true)
  studio.emit('focus')
  expect(reloadMenuItem.enabled).toBe(false)
})

it('wires project file selection and denies Studio and subframe callers', async () => {
  const main = FakeWindow.instances[0]!
  const studioWindow = await openStudio()
  expect(handlers.has('autoflow:project-files:choose-excel-input')).toBe(true)
  expect(handlers.has('autoflow:project-files:choose-xlsx-output')).toBe(true)
  await expect(invoke('autoflow:project-files:choose-excel-input', studioWindow, '726a0f9e-a0e7-4b83-9794-b8d5946825e0')).resolves.toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
  await expect(handlers.get('autoflow:project-files:choose-excel-input')!({ ...sender(main), senderFrame: {} }, '726a0f9e-a0e7-4b83-9794-b8d5946825e0')).resolves.toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
})
