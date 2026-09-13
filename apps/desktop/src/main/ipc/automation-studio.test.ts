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
const frame = {}
const event = (senderId = 7, senderFrame: unknown = frame) => ({
  sender: { id: senderId, mainFrame: frame }, senderFrame,
})
beforeEach(async () => {
  vi.resetModules()
  FakeWindow.instances = []
  mainId = 7
  vi.doMock('electron', () => ({ BrowserWindow: FakeWindow, dialog: { showMessageBoxSync: vi.fn(() => 1) } }))
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
  window.close()
  expect(window.destroyed).toBe(true)
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

it('only allows the current main window to reuse Studio after the main window is recreated', async () => {
  await studio.open(event())
  mainId = 8
  await expect(studio.open(event())).rejects.toThrow()
  await studio.open(event(8))
  expect(FakeWindow.instances).toHaveLength(1)
})

it('denies new windows and navigation away from the fixed renderer', async () => {
  await studio.open(event())
  const contents = FakeWindow.instances[0]!.webContents
  const openHandler = contents.setWindowOpenHandler.mock.calls[0]![0] as () => unknown
  expect(openHandler()).toEqual({ action: 'deny' })
  const navigation = { preventDefault: vi.fn() }
  contents.emit('will-navigate', navigation)
  expect(navigation.preventDefault).toHaveBeenCalledOnce()
})

it('lets the renderer veto quit and accepts only an explicit discard', async()=>{
  await studio.open(event())
  const window=FakeWindow.instances[0]!
  const veto={preventDefault:vi.fn()}
  const {dialog}=await import('electron')
  window.webContents.emit('will-prevent-unload',veto)
  expect(veto.preventDefault).not.toHaveBeenCalled()
  vi.mocked(dialog.showMessageBoxSync).mockReturnValue(0)
  window.webContents.emit('will-prevent-unload',veto)
  expect(veto.preventDefault).toHaveBeenCalledOnce()
  expect(await studio.closeForQuit()).toBe(true)
})
