import { EventEmitter } from 'node:events'
import { beforeEach, expect, it, vi } from 'vitest'

class FakeWindow extends EventEmitter {
  static instances: FakeWindow[] = []
  destroyed = false
  minimized = false
  webContents = Object.assign(new EventEmitter(), { id: 100 + FakeWindow.instances.length, mainFrame: {}, setWindowOpenHandler: vi.fn(), setZoomFactor: vi.fn(), send: vi.fn() })
  loadURL = vi.fn(async (_url: string) => {})
  loadFile = vi.fn(async (_path: string, _options: unknown) => {})
  show = vi.fn()
  focus = vi.fn()
  setTitle = vi.fn()
  restore = vi.fn(() => { this.minimized = false })
  isDestroyed() { return this.destroyed }
  isMinimized() { return this.minimized }
  destroy() { this.destroyed = true; this.emit('closed') }
  close() { const event = { preventDefault: vi.fn() }; this.emit('close', event); if (!event.preventDefault.mock.calls.length) this.destroy() }
  constructor(readonly options: Record<string, unknown>) {
    super()
    FakeWindow.instances.push(this)
  }
}

let studio: import('./automation-studio').StudioWindowController
let mainId: number
const reloadItem = { role: 'reload', enabled: true }
const forceReloadItem = { role: 'forceReload', enabled: false }
const copyItem = { role: 'copy', enabled: true }
const menu = { items: [{ submenu: { items: [reloadItem, forceReloadItem, copyItem] } }] }
const frame = {}
const event = (senderId = 7, senderFrame: unknown = frame) => ({
  sender: { id: senderId, mainFrame: frame }, senderFrame,
})
const studioEvent = () => {
  const sender = FakeWindow.instances.at(-1)!.webContents
  return { sender, senderFrame: sender.mainFrame }
}
const latestRequest = () => FakeWindow.instances.at(-1)!.webContents.send.mock.calls.slice().reverse().find(call => call[0] === 'autoflow:studio-prepare-leave')![1] as { id: string; reason: string }

beforeEach(async () => {
  vi.resetModules()
  FakeWindow.instances = []
  mainId = 7
  reloadItem.enabled = true; forceReloadItem.enabled = false; copyItem.enabled = true
  vi.doMock('electron', () => ({ BrowserWindow: FakeWindow, Menu: { getApplicationMenu: () => menu } }))
  studio = new (await import('./automation-studio')).StudioWindowController({ mainSenderId: () => mainId, preferences: () => ({ zoom: 110, motion: 'reduce' }), preloadPath: '/preload/index.js', rendererFile: '/renderer/index.html', rendererUrl: 'http://localhost:5173/' })
})

it('opens one independent formal renderer, restores it, and allows reopening after close', async () => {
  await Promise.all([studio.open(event()), studio.open(event())])
  expect(FakeWindow.instances).toHaveLength(1)
  const window = FakeWindow.instances[0]!
  expect(window.loadURL).toHaveBeenCalledWith('http://localhost:5173/?view=automation-studio')
  expect(window.options).toMatchObject({
    title: '工作流工作台 · AutoFlow',
    webPreferences: { preload: '/preload/index.js', contextIsolation: true, sandbox: true, nodeIntegration: false },
  })
  expect(window.options).not.toHaveProperty('parent')
  expect(window.show).toHaveBeenCalled()
  window.minimized = true
  await studio.open(event())
  expect(window.restore).toHaveBeenCalledOnce()
  expect(FakeWindow.instances).toHaveLength(1)
  window.destroy()
  await studio.open(event())
  expect(FakeWindow.instances).toHaveLength(2)
})

it('rejects other renderers and subframes without creating a window', async () => {
  for (const unauthorized of [event(8), event(7, {}), event(7, null)]) {
    await expect(studio.open(unauthorized)).rejects.toThrow('此窗口不能打开工作流工作台')
  }
  expect(FakeWindow.instances).toHaveLength(0)
})

it('cleans up a failed load so a later click can retry', async () => {
  vi.doMock('electron', () => ({ BrowserWindow: class extends FakeWindow {
    constructor(options: Record<string, unknown>) {
      super(options)
      if (FakeWindow.instances.length === 1) this.loadURL.mockRejectedValueOnce(new Error('load failed'))
    }
  } }))
  vi.resetModules()
  const fail = new (await import('./automation-studio')).StudioWindowController({ mainSenderId: () => 7, preferences: () => ({ zoom: 100, motion: 'system' }), preloadPath: '/preload/index.js', rendererFile: '/renderer/index.html', rendererUrl: 'http://localhost:5173' })
  await expect(fail.open(event())).rejects.toThrow('无法打开工作流工作台，请重试')
  expect(FakeWindow.instances[0]?.destroyed).toBe(true)
  await fail.open(event())
  expect(FakeWindow.instances).toHaveLength(2)
  expect(FakeWindow.instances[1]?.show).toHaveBeenCalled()
})

it('uses the same packaged HTML and applies preferences after loading', async () => {
  const packaged = new (await import('./automation-studio')).StudioWindowController({ mainSenderId: () => 7, preferences: () => ({ zoom: 125, motion: 'reduce' }), preloadPath: '/preload/index.js', rendererFile: '/renderer/index.html' })
  await packaged.open(event())
  const window = FakeWindow.instances[0]!
  expect(window.loadFile).toHaveBeenCalledWith('/renderer/index.html', { query: { view: 'automation-studio' } })
  window.webContents.emit('did-finish-load')
  expect(window.webContents.setZoomFactor).toHaveBeenCalledWith(1.25)
  expect(window.webContents.send).toHaveBeenCalledWith('autoflow:preferences-changed', { zoom: 125, motion: 'reduce' })
})

it('protects ordinary close until the current renderer approves it', async () => {
  await studio.open(event())
  studio.markReady(studioEvent(), true)
  const window = FakeWindow.instances[0]!
  window.close()
  expect(window.destroyed).toBe(false)
  const first = latestRequest()
  expect(first.reason).toBe('close')
  expect(() => studio.reply(event(), first.id, true)).toThrow()
  expect(() => studio.reply({ ...studioEvent(), senderFrame: {} }, first.id, true)).toThrow()
  studio.reply(studioEvent(), 'stale-request', true)
  expect(window.destroyed).toBe(false)
  studio.reply(studioEvent(), first.id, false)
  await Promise.resolve()
  expect(window.destroyed).toBe(false)
  window.close()
  studio.reply(studioEvent(), latestRequest().id, true)
  await vi.waitFor(() => expect(window.destroyed).toBe(true))
})

it('serializes transitions, stays locked after approval, and unlocks after a failed action', async () => {
  await studio.open(event())
  studio.markReady(studioEvent(), true)
  const pending = studio.prepareLeave('workspace')
  expect(await studio.prepareLeave('quit')).toBe(false)
  studio.reply(studioEvent(), latestRequest().id, true)
  expect(await pending).toBe(true)
  expect(studio.isTransitioning()).toBe(true)
  await expect(studio.open(event())).rejects.toThrow('工作区正在切换')
  studio.finishTransition()
  expect(studio.isTransitioning()).toBe(false)
  expect(FakeWindow.instances[0]!.webContents.send).toHaveBeenLastCalledWith('autoflow:studio-transition', false)
})

it('fails closed if the renderer crashes while asking about unsaved edits', async () => {
  await studio.open(event())
  studio.markReady(studioEvent(), true)
  const pending = studio.prepareLeave('quit')
  FakeWindow.instances[0]!.webContents.emit('render-process-gone')
  expect(await pending).toBe(false)
  expect(studio.isTransitioning()).toBe(false)
})

it('keeps Studio authorized when the main window is recreated', async () => {
  await studio.open(event())
  const registered = studioEvent()
  mainId = 8
  expect(studio.isSender(registered)).toBe(true)
  await expect(studio.open(event())).rejects.toThrow()
  await studio.open(event(8))
  expect(FakeWindow.instances).toHaveLength(1)
})

it('allows application quit triggered by the last window closing', async () => {
  await studio.open(event())
  studio.markReady(studioEvent(), true)
  const window = FakeWindow.instances[0]!
  let quit: Promise<boolean> | undefined
  window.once('closed', () => { quit = studio.prepareLeave('quit') })
  window.close()
  studio.reply(studioEvent(), latestRequest().id, true)
  await vi.waitFor(() => expect(window.destroyed).toBe(true))
  expect(await quit).toBe(true)
})

it('restores and focuses a minimized Studio before a workspace save question', async () => {
  await studio.open(event())
  studio.markReady(studioEvent(), true)
  const window = FakeWindow.instances[0]!
  window.minimized = true
  window.focus.mockClear(); window.show.mockClear()
  const pending = studio.prepareLeave('workspace')
  expect(window.restore).toHaveBeenCalledOnce()
  expect(window.show).toHaveBeenCalledOnce()
  expect(window.focus).toHaveBeenCalledOnce()
  studio.reply(studioEvent(), latestRequest().id, false)
  expect(await pending).toBe(false)
})

it('blocks reload and force-reload shortcuts without intercepting typing or save', async () => {
  await studio.open(event())
  const contents = FakeWindow.instances[0]!.webContents
  for (const input of [{ key: 'F5' }, { key: 'F5', control: true }, { key: 'r', control: true }, { key: 'R', meta: true }, { key: 'r', meta: true, shift: true }, { key: 'r', control: true, shift: true }]) {
    const keyEvent = { preventDefault: vi.fn() }
    contents.emit('before-input-event', keyEvent, input)
    expect(keyEvent.preventDefault).toHaveBeenCalledOnce()
  }
  for (const input of [{ key: 'r' }, { key: 's', meta: true }, { key: 'z', control: true }]) {
    const keyEvent = { preventDefault: vi.fn() }
    contents.emit('before-input-event', keyEvent, input)
    expect(keyEvent.preventDefault).not.toHaveBeenCalled()
  }
})

it('disables only existing reload menu entries while focused and restores their original state', async () => {
  await studio.open(event())
  const window = FakeWindow.instances[0]!
  window.emit('focus')
  window.emit('focus')
  expect(reloadItem.enabled).toBe(false)
  expect(forceReloadItem.enabled).toBe(false)
  expect(copyItem.enabled).toBe(true)
  studio.restoreReloadMenu()
  expect(reloadItem.enabled).toBe(true)
  expect(forceReloadItem.enabled).toBe(false)
  window.emit('focus')
  expect(reloadItem.enabled).toBe(false)
  window.destroy()
  expect(reloadItem.enabled).toBe(true)
  expect(forceReloadItem.enabled).toBe(false)
})
