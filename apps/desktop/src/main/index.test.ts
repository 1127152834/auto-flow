// @vitest-environment node
import { EventEmitter } from 'node:events'
import { afterEach, beforeEach, expect, it, vi, type Mock } from 'vitest'
import type { DesktopIpcEvent } from './ipc/automation-studio'
import type { SettingsControllerOptions } from './settings/controller'
import type { DesktopRuntimeContext } from '../shared/runtime'

class FakeWindow extends EventEmitter {
  static instances: FakeWindow[] = []
  destroyed = false
  unsaved = false
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
  close() { if (this.unsaved) { const veto={preventDefault:vi.fn()}; this.webContents.emit('will-prevent-unload',veto); if (!veto.preventDefault.mock.calls.length) return } const event = { preventDefault: vi.fn() }; this.emit('close', event); if (!event.preventDefault.mock.calls.length) this.destroy() }
  constructor(readonly options?: {webPreferences?: {partition?: string}}) { super(); FakeWindow.instances.push(this) }
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
  vi.doMock('node:fs', async () => ({...await vi.importActual<typeof import('node:fs')>('node:fs'), realpathSync: (path: string) => path.replace('/alias/', '/')}))
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
  vi.doMock('electron', () => ({ app, BrowserWindow: FakeWindow, globalShortcut: { register: vi.fn(() => true), unregister: vi.fn() }, ipcMain: { handle: (name: string, handler: (event: DesktopIpcEvent, ...args: unknown[]) => unknown) => handlers.set(name, handler), removeHandler: (name: string) => handlers.delete(name) }, clipboard: {}, shell: { openExternal: vi.fn(async () => {}), openPath: vi.fn(), showItemInFolder: vi.fn() }, dialog: { showErrorBox: vi.fn(), showMessageBoxSync: vi.fn(()=>1) } }))
  vi.doMock('./settings/controller', () => ({ SettingsController: class {
    constructor(private options: SettingsControllerOptions) {}
    start = async () => {}
    shutdown = settings.shutdown
    confirmWorkspace = settings.confirmWorkspace
    restart = settings.restart
    getRuntimeContext = () => context
    getStatus = () => context.sidecar
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
afterEach(() => { vi.unstubAllGlobals(); vi.doUnmock('electron'); vi.doUnmock('./settings/controller'); vi.doUnmock('node:fs') })

async function openStudio() {
  await invoke('autoflow:open-automation-studio', FakeWindow.instances[0]!)
  return FakeWindow.instances[1]!
}

function answerLeave(window:FakeWindow,allowed=true){
 invoke('autoflow:studio-leave-ready',window)
 window.webContents.send.mockImplementation((channel:string,request?:{id:string})=>{
  if(channel==='autoflow:studio-prepare-leave')invoke('autoflow:studio-leave-result',window,{id:request!.id,allowed})
 })
}

it('allows registered Studio runtime reads while protecting mutations and gating service restart', async () => {
  const main = FakeWindow.instances[0]!
  const studio = await openStudio()
  expect(invoke('autoflow:runtime-context', main)).toEqual(context)
  expect(invoke('autoflow:runtime-context', studio)).toEqual(context)
  expect(invoke('autoflow:sidecar-status', studio)).toEqual(context.sidecar)
  expect(() => handlers.get('autoflow:runtime-context')!({ ...sender(main), senderFrame: {} })).toThrow()
  const stranger = new FakeWindow()
  expect(() => invoke('autoflow:runtime-context', stranger)).toThrow()
  await expect(invoke('autoflow:settings:preferences', studio, {})).resolves.toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
  await expect(invoke('autoflow:copy-proxy-credentials', studio, {})).rejects.toThrow()
  answerLeave(studio,false)
  await expect(invoke('autoflow:sidecar-restart', studio)).rejects.toThrow('请先结束')
  expect(settings.restart).not.toHaveBeenCalled()
  answerLeave(studio,true)
  await expect(invoke('autoflow:sidecar-restart', main)).resolves.toEqual(context.sidecar)
  expect(settings.restart).toHaveBeenCalledOnce()
  expect(JSON.stringify(invoke('autoflow:runtime-context', main))).not.toContain('hostToken')

  context = { ...context, sidecar: { state: 'failed', message: 'sidecar exited with code unknown' } }
  studio.webContents.send.mockClear()
  await expect(invoke('autoflow:sidecar-restart', main)).resolves.toEqual(context.sidecar)
  expect(settings.restart).toHaveBeenCalledTimes(2)
  expect(studio.webContents.send).not.toHaveBeenCalledWith('autoflow:studio-prepare-leave', expect.anything())
})

it('switches workspace only after Studio acknowledgement and recreates its isolated window', async () => {
  const main = FakeWindow.instances[0]!
  const studio = await openStudio()
  answerLeave(studio)
  await expect(invoke('autoflow:settings:confirm-workspace', main, 'choice')).resolves.toMatchObject({ ok: true })
  expect(settings.confirmWorkspace).toHaveBeenCalledWith('choice')
  expect(main.webContents.send).toHaveBeenLastCalledWith('autoflow:runtime-context-changed', context)
  expect(studio.webContents.send.mock.calls.map(call => call[0])).not.toContain('autoflow:runtime-context-changed')
  expect(handlers.has('autoflow:studio-ready')).toBe(false)
  expect(handlers.has('autoflow:studio-leave-result')).toBe(true)
  expect(studio.destroyed).toBe(true)
  expect(FakeWindow.instances).toHaveLength(3)
  expect(handlers.has('autoflow:workflow-export')).toBe(false)
})

it('keeps the old workspace and open windows on switch failure', async () => {
  const main = FakeWindow.instances[0]!
  const studio = await openStudio()
  settings.confirmWorkspace.mockRejectedValueOnce(new Error('target failed'))
  answerLeave(studio)
  await expect(invoke('autoflow:settings:confirm-workspace', main, 'choice')).resolves.toMatchObject({ ok: false })
  expect(context.workspaceKey).toBe('/workspace-a')
  expect(main.webContents.send).toHaveBeenLastCalledWith('autoflow:runtime-context-changed', context)
  expect(studio.destroyed).toBe(false)
})

it('closes Studio before stopping the sidecar and quitting the main window', async () => {
  const studio = await openStudio()
  let finishShutdown!: () => void
  settings.shutdown.mockImplementationOnce(() => new Promise<void>(resolve => { finishShutdown = resolve }))
  app.quit()
  await vi.waitFor(()=>expect(settings.shutdown).toHaveBeenCalledOnce())
  expect(studio.destroyed).toBe(true)
  expect(FakeWindow.instances[0]!.destroyed).toBe(false)
  finishShutdown()
  await vi.waitFor(() => expect(FakeWindow.instances[0]!.destroyed).toBe(true))
})

it('keeps the main window on shutdown failure and permits retry', async () => {
  await openStudio()
  settings.shutdown.mockRejectedValueOnce(new Error('cleanup failed'))
  app.quit()
  const {dialog}=await import('electron')
  await vi.waitFor(()=>expect(dialog.showErrorBox).toHaveBeenCalledOnce())
  expect(FakeWindow.instances[0]!.destroyed).toBe(false)
  app.quit()
  await vi.waitFor(() => expect(FakeWindow.instances[0]!.destroyed).toBe(true))
  expect(settings.shutdown).toHaveBeenCalledTimes(2)
})

it('does not shut down the sidecar when the user keeps the unsaved Studio open',async()=>{
  const studio=await openStudio();studio.unsaved=true
  app.quit()
  await Promise.resolve();await Promise.resolve()
  expect(settings.shutdown).not.toHaveBeenCalled()
  expect(studio.destroyed).toBe(false)
  const {dialog}=await import('electron')
  vi.mocked(dialog.showMessageBoxSync).mockReturnValue(0)
  app.quit()
  await vi.waitFor(()=>expect(settings.shutdown).toHaveBeenCalledOnce())
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
it('wires project file selection and denies Studio and subframe callers', async () => {
  const main = FakeWindow.instances[0]!
  const studioWindow = await openStudio()
  expect(handlers.has('autoflow:project-files:choose-excel-input')).toBe(true)
  expect(handlers.has('autoflow:project-files:choose-xlsx-output')).toBe(true)
  await expect(invoke('autoflow:project-files:choose-excel-input', studioWindow, '726a0f9e-a0e7-4b83-9794-b8d5946825e0')).resolves.toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
  await expect(handlers.get('autoflow:project-files:choose-excel-input')!({ ...sender(main), senderFrame: {} }, '726a0f9e-a0e7-4b83-9794-b8d5946825e0')).resolves.toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
})

it('registers controlled record links for the main frame only', async () => {
  const main = FakeWindow.instances[0]!
  expect(await invoke('autoflow:open-external-link', main, 'https://example.com')).toEqual({ ok: true, value: { opened: true } })
  const studio = await openStudio()
  expect(await invoke('autoflow:open-external-link', studio, 'https://example.com')).toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
})

it('uses the same renderer storage partition for aliases of the same workspace', async () => {
 context.workspaceKey = '/alias/workspace-a'
 const first = await openStudio()
 const partition = first.options?.webPreferences?.partition
 first.destroy()
 context.workspaceKey = '/workspace-a'
 await invoke('autoflow:open-automation-studio', FakeWindow.instances[0]!)
 expect(FakeWindow.instances.at(-1)?.options?.webPreferences?.partition).toBe(partition)
 expect(partition).toMatch(/^persist:studio-/)
})
