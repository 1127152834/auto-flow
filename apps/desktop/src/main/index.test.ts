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
const sender = (window: FakeWindow) => ({ sender: window.webContents, senderFrame: window.webContents.mainFrame })
const invoke = (channel: string, window: FakeWindow, ...args: unknown[]) => handlers.get(channel)!(sender(window), ...args)

beforeEach(async () => {
  vi.resetModules()
  vi.stubGlobal('__dirname', '/compiled/main')
  FakeWindow.instances = []
  handlers = new Map()
  context = runtime()
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
  vi.doMock('electron', () => ({ app, BrowserWindow: FakeWindow, ipcMain: { handle: (name: string, handler: (event: DesktopIpcEvent, ...args: unknown[]) => unknown) => handlers.set(name, handler), removeHandler: (name: string) => handlers.delete(name) }, clipboard: {}, shell: { openPath: vi.fn(), showItemInFolder: vi.fn() }, dialog: { showErrorBox: vi.fn() } }))
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
  return FakeWindow.instances[1]!
}

it('keeps service credentials, restart, settings and credential mutations main-only', async () => {
  const main = FakeWindow.instances[0]!
  const studio = await openStudio()
  expect(invoke('autoflow:runtime-context', main)).toEqual(context)
  expect(() => invoke('autoflow:runtime-context', studio)).toThrow()
  expect(() => invoke('autoflow:sidecar-status', studio)).toThrow()
  expect(() => handlers.get('autoflow:runtime-context')!({ ...sender(main), senderFrame: {} })).toThrow()
  const stranger = new FakeWindow()
  expect(() => invoke('autoflow:runtime-context', stranger)).toThrow()
  await expect(invoke('autoflow:settings:preferences', studio, {})).resolves.toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
  await expect(invoke('autoflow:copy-proxy-credentials', studio, {})).rejects.toThrow()
  await expect(invoke('autoflow:sidecar-restart', studio)).rejects.toThrow()
  expect(settings.restart).not.toHaveBeenCalled()
  await expect(invoke('autoflow:sidecar-restart', main)).resolves.toEqual(context.sidecar)
  expect(settings.restart).toHaveBeenCalledOnce()
  expect(JSON.stringify(invoke('autoflow:runtime-context', main))).not.toContain('hostToken')
})

it('switches workspace without a Studio handshake and publishes credentials only to main', async () => {
  const main = FakeWindow.instances[0]!
  const studio = await openStudio()
  await expect(invoke('autoflow:settings:confirm-workspace', main, 'choice')).resolves.toMatchObject({ ok: true })
  expect(settings.confirmWorkspace).toHaveBeenCalledWith('choice')
  expect(main.webContents.send).toHaveBeenLastCalledWith('autoflow:runtime-context-changed', context)
  expect(studio.webContents.send.mock.calls.map(call => call[0])).not.toContain('autoflow:runtime-context-changed')
  expect(handlers.has('autoflow:studio-ready')).toBe(false)
  expect(handlers.has('autoflow:studio-leave-result')).toBe(false)
  expect(handlers.has('autoflow:workflow-export')).toBe(false)
})

it('keeps the old workspace and open windows on switch failure', async () => {
  const main = FakeWindow.instances[0]!
  const studio = await openStudio()
  settings.confirmWorkspace.mockRejectedValueOnce(new Error('target failed'))
  await expect(invoke('autoflow:settings:confirm-workspace', main, 'choice')).resolves.toMatchObject({ ok: false })
  expect(context.workspaceKey).toBe('/workspace-a')
  expect(main.webContents.send).toHaveBeenLastCalledWith('autoflow:runtime-context-changed', context)
  expect(studio.destroyed).toBe(false)
})

it('stops the sidecar before quitting and closing the empty Studio', async () => {
  const studio = await openStudio()
  let finishShutdown!: () => void
  settings.shutdown.mockImplementationOnce(() => new Promise<void>(resolve => { finishShutdown = resolve }))
  app.quit()
  expect(settings.shutdown).toHaveBeenCalledOnce()
  expect(studio.destroyed).toBe(false)
  finishShutdown()
  await vi.waitFor(() => expect(studio.destroyed).toBe(true))
})

it('keeps windows open after failed shutdown and permits a later retry', async () => {
  const studio = await openStudio()
  settings.shutdown.mockRejectedValueOnce(new Error('cleanup failed'))
  app.quit()
  await Promise.resolve(); await Promise.resolve()
  expect(studio.destroyed).toBe(false)
  app.quit()
  await vi.waitFor(() => expect(studio.destroyed).toBe(true))
  expect(settings.shutdown).toHaveBeenCalledTimes(2)
})

it('keeps Studio alive when the main window closes and permits reuse from its replacement', async () => {
  const studio = await openStudio()
  const original = FakeWindow.instances[0]!
  original.close()
  expect(studio.destroyed).toBe(false)
  expect(settings.shutdown).not.toHaveBeenCalled()
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
