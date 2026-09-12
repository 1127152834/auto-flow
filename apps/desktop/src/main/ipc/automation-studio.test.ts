import { EventEmitter } from 'node:events'
import { beforeEach, expect, it, vi } from 'vitest'

class FakeWindow extends EventEmitter {
  static instances: FakeWindow[] = []
  destroyed = false
  minimized = false
  webContents = Object.assign(new EventEmitter(), { setWindowOpenHandler: vi.fn() })
  loadURL = vi.fn(async (_url: string) => {})
  show = vi.fn()
  focus = vi.fn()
  setTitle = vi.fn()
  restore = vi.fn(() => { this.minimized = false })
  isDestroyed() { return this.destroyed }
  isMinimized() { return this.minimized }
  destroy() { this.destroyed = true; this.emit('closed') }
  constructor(readonly options: Record<string, unknown>) {
    super()
    FakeWindow.instances.push(this)
  }
}

let handler: ReturnType<typeof import('./automation-studio')['createOpenAutomationStudioHandler']>
const frame = {}
const event = (senderId = 7, senderFrame: unknown = frame) => ({
  sender: { id: senderId, mainFrame: frame }, senderFrame,
}) as Parameters<typeof handler>[0]

beforeEach(async () => {
  vi.resetModules()
  FakeWindow.instances = []
  vi.doMock('electron', () => ({ BrowserWindow: FakeWindow }))
  handler = (await import('./automation-studio')).createOpenAutomationStudioHandler(7)
})

it('opens one independent empty window, restores it, and allows reopening after close', async () => {
  await Promise.all([handler(event()), handler(event())])
  expect(FakeWindow.instances).toHaveLength(1)
  const window = FakeWindow.instances[0]!
  expect(window.loadURL).toHaveBeenCalledWith('about:blank')
  expect(window.options).toMatchObject({
    title: '工作流工作台 · AutoFlow',
    webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false },
  })
  expect(window.options).not.toHaveProperty('parent')
  expect(window.options.webPreferences).not.toHaveProperty('preload')
  expect(window.show).toHaveBeenCalled()
  window.minimized = true
  await handler(event())
  expect(window.restore).toHaveBeenCalledOnce()
  expect(FakeWindow.instances).toHaveLength(1)
  window.destroy()
  await handler(event())
  expect(FakeWindow.instances).toHaveLength(2)
})

it('rejects other renderers and subframes without creating a window', async () => {
  for (const unauthorized of [event(8), event(7, {}), event(7, null)]) {
    await expect(handler(unauthorized)).rejects.toThrow('此窗口不能打开工作流工作台')
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
  const fail = (await import('./automation-studio')).createOpenAutomationStudioHandler(7)
  await expect(fail(event())).rejects.toThrow('无法打开工作流工作台，请重试')
  expect(FakeWindow.instances[0]?.destroyed).toBe(true)
  await fail(event())
  expect(FakeWindow.instances).toHaveLength(2)
  expect(FakeWindow.instances[1]?.show).toHaveBeenCalled()
})
