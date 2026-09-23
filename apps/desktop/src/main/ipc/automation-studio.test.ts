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

it('passes the project workflow context to the isolated renderer', async () => {
  await studio.open(event(), { workspaceKey: 'workspace', instanceId: 'instance', projectId: 'project', workflowId: 'workflow' })
  expect(FakeWindow.instances[0]!.loadURL).toHaveBeenCalledWith(
    'http://localhost:5173/?view=automation-studio&workspaceKey=workspace&instanceId=instance&projectId=project&workflowId=workflow',
  )
})

it('uses the existing leave guard before switching the Studio project context', async () => {
  await studio.open(event())
  const source = FakeWindow.instances[0]!
  const sender = { sender: source.webContents, senderFrame: source.webContents.mainFrame }
  studio.registerLeaveReady(sender)
  const switching = studio.open(event(), { projectId: 'project', workflowId: 'workflow' })
  const request = source.webContents.send.mock.calls.find(call => call[0] === 'autoflow:studio-prepare-leave')![1]
  expect(source.destroyed).toBe(false)
  studio.completeLeave(sender, { id: request.id, allowed: true })
  await switching
  expect(source.destroyed).toBe(true)
  expect(FakeWindow.instances).toHaveLength(2)
  expect(FakeWindow.instances[1]!.loadURL).toHaveBeenCalledWith(
    'http://localhost:5173/?view=automation-studio&projectId=project&workflowId=workflow',
  )
})

it('rejects other renderers and subframes without creating a window', async () => {
  for (const unauthorized of [event(8), event(7, {}), event(7, null)]) {
    await expect(studio.open(unauthorized)).rejects.toThrow('此窗口不能打开工作流工作台')
  }
  expect(FakeWindow.instances).toHaveLength(0)
})

it('delivers shortcuts only to the ready current Studio outside pending leave', async () => {
  const invalidate = vi.fn()
  studio = new (await import('./automation-studio')).StudioWindowController({
    mainSenderId: () => mainId, preferences: () => ({ zoom: 100, motion: 'reduce' }),
    preloadPath: '/preload/index.js', rendererFile: '/renderer/studio.html', onInvalidated: invalidate,
  })
  expect(studio.senderId()).toBeUndefined()
  await studio.open(event())
  const window = FakeWindow.instances[0]!
  const sender = { sender: window.webContents, senderFrame: window.webContents.mainFrame }
  expect(studio.senderId()).toBe(window.webContents.id)
  studio.sendHotkey('save_workflow')
  expect(window.webContents.send).not.toHaveBeenCalledWith('autoflow:studio-hotkey', 'save_workflow')
  studio.registerLeaveReady(sender)
  studio.sendHotkey('save_workflow')
  expect(window.webContents.send).toHaveBeenCalledWith('autoflow:studio-hotkey', 'save_workflow')
  window.webContents.send.mockClear()
  const leaving = studio.prepareLeave('close')
  studio.sendHotkey('run_workflow')
  expect(window.webContents.send).not.toHaveBeenCalledWith('autoflow:studio-hotkey', 'run_workflow')
  const request = window.webContents.send.mock.calls[0]![1]
  studio.completeLeave(sender, { id: request.id, allowed: false })
  expect(await leaving).toBe(false)
  studio.sendHotkey('run_workflow')
  expect(window.webContents.send).toHaveBeenCalledWith('autoflow:studio-hotkey', 'run_workflow')
  window.webContents.emit('did-start-loading')
  window.webContents.emit('render-process-gone')
  window.destroy()
  expect(invalidate).toHaveBeenCalledTimes(3)
  expect(studio.senderId()).toBeUndefined()
})

it('rejects malformed project context instead of silently opening an unscoped window', async () => {
  for (const context of [null, [], 'project', { projectId: 7 }, { projectId: '' }, { workflowId: ' '.repeat(3) }, { workspaceKey: 'x'.repeat(201) }]) {
    await expect(studio.open(event(), context)).rejects.toThrow('工作台上下文无效')
  }
  expect(FakeWindow.instances).toHaveLength(0)
})

it('coalesces the same context switch and rejects competing destinations', async () => {
  await studio.open(event(), { projectId: 'source' })
  const source = FakeWindow.instances[0]!
  const sender = { sender: source.webContents, senderFrame: source.webContents.mainFrame }
  studio.registerLeaveReady(sender)
  const first = studio.open(event(), { projectId: 'destination' })
  const repeat = studio.open(event(), { projectId: 'destination' })
  await expect(studio.open(event(), { projectId: 'other' })).rejects.toThrow('正在切换')
  const request = source.webContents.send.mock.calls.find(call => call[0] === 'autoflow:studio-prepare-leave')![1]
  studio.completeLeave(sender, { id: request.id, allowed: true })
  await Promise.all([first, repeat])
  expect(FakeWindow.instances).toHaveLength(2)
  expect(FakeWindow.instances[1]!.isDestroyed()).toBe(false)
  expect(FakeWindow.instances[1]!.loadURL).toHaveBeenCalledWith('http://localhost:5173/?view=automation-studio&projectId=destination')
})

it('retains the original project and document when switching is cancelled', async () => {
  const context = { projectId: 'source', workflowId: 'draft' }
  await studio.open(event(), context)
  const source = FakeWindow.instances[0]!
  const sender = { sender: source.webContents, senderFrame: source.webContents.mainFrame }
  studio.registerLeaveReady(sender)
  const switching = studio.open(event(), { projectId: 'destination' })
  const rejected = expect(switching).rejects.toThrow('未保存修改')
  const request = source.webContents.send.mock.calls.find(call => call[0] === 'autoflow:studio-prepare-leave')![1]
  studio.completeLeave(sender, { id: request.id, allowed: false })
  await rejected
  await studio.open(event(), context)
  expect(FakeWindow.instances).toHaveLength(1)
  expect(source.isDestroyed()).toBe(false)
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

it('waits for the registered Studio save/cleanup decision and coalesces repeated quit requests',async()=>{
 await studio.open(event());const window=FakeWindow.instances[0]!
 const sender={sender:window.webContents,senderFrame:window.webContents.mainFrame}
 studio.registerLeaveReady(sender)
 window.minimized=true;window.focus.mockClear()
 const first=studio.closeForQuit(),second=studio.closeForQuit()
 expect(window.restore).toHaveBeenCalledOnce()
 expect(window.focus).toHaveBeenCalledOnce()
 const message=window.webContents.send.mock.calls.find(call=>call[0]==='autoflow:studio-prepare-leave')![1]
 expect(window.destroyed).toBe(false)
 expect(window.webContents.send.mock.calls.filter(call=>call[0]==='autoflow:studio-prepare-leave')).toHaveLength(1)
 studio.completeLeave(sender,{id:message.id,allowed:false})
 expect(await first).toBe(false);expect(await second).toBe(false);expect(window.destroyed).toBe(false)
 const retry=studio.closeForQuit()
 const next=window.webContents.send.mock.calls.filter(call=>call[0]==='autoflow:studio-prepare-leave').at(-1)![1]
 expect(()=>studio.completeLeave(sender,{id:message.id,allowed:true})).toThrow('过期')
 studio.completeLeave(sender,{id:next.id,allowed:true})
 expect(await retry).toBe(true);expect(window.destroyed).toBe(true)
})
it('protects native close and rejects another window or child-frame acknowledgement',async()=>{
 await studio.open(event());const window=FakeWindow.instances[0]!
 const sender={sender:window.webContents,senderFrame:window.webContents.mainFrame}
 expect(()=>studio.registerLeaveReady(event())).toThrow()
 studio.registerLeaveReady(sender);window.close()
 const message=window.webContents.send.mock.calls.filter(call=>call[0]==='autoflow:studio-prepare-leave').at(-1)![1]
 expect(window.destroyed).toBe(false)
 expect(()=>studio.completeLeave({...sender,senderFrame:{}},{id:message.id,allowed:true})).toThrow()
 studio.completeLeave(sender,{id:message.id,allowed:true})
 await vi.waitFor(()=>expect(window.destroyed).toBe(true))
})
it('does not treat a crashed renderer as approval to leave',async()=>{
 await studio.open(event());const window=FakeWindow.instances[0]!
 studio.registerLeaveReady({sender:window.webContents,senderFrame:window.webContents.mainFrame})
 const pending=studio.closeForQuit();window.webContents.emit('render-process-gone')
 expect(await pending).toBe(false);expect(window.destroyed).toBe(false)
})
it('keeps the source window on workspace failure and opens an isolated partition only after success',async()=>{
 let partition='persist:workspace-a'
 const controller=new (await import('./automation-studio')).StudioWindowController({mainSenderId:()=>7,preferences:()=>({zoom:100,motion:'system'}),preloadPath:'/preload',rendererFile:'/studio.html',workspacePartition:()=>partition})
 await controller.open(event(),{workspaceKey:'workspace-a',instanceId:'instance-a',projectId:'project-a',workflowId:'workflow-a'});const source=FakeWindow.instances[0]!
 await controller.finishWorkspaceTransition(false)
 expect(source.destroyed).toBe(false)
 expect(source.webContents.send).toHaveBeenCalledWith('autoflow:studio-transition-end')
 expect(source.loadFile).toHaveBeenCalledWith('/studio.html',{query:{view:'automation-studio',workspaceKey:'workspace-a',instanceId:'instance-a',projectId:'project-a',workflowId:'workflow-a'}})
 partition='persist:workspace-b';await controller.finishWorkspaceTransition(true)
 expect(source.destroyed).toBe(true)
 expect(FakeWindow.instances[1]!.options.webPreferences).toMatchObject({partition:'persist:workspace-b'})
 expect(FakeWindow.instances[1]!.loadFile).toHaveBeenCalledWith('/studio.html',{query:{view:'automation-studio'}})
})

 it('retains the main renderer only while Studio remains open, without blocking app quit', async () => {
  const { retainMainWindowForStudio } = await import('./automation-studio')
  const main = { hide: vi.fn() }; const close = { preventDefault: vi.fn() }
  retainMainWindowForStudio(close, main, undefined, false)
  expect(close.preventDefault).not.toHaveBeenCalled()
  retainMainWindowForStudio(close, main, 101, false)
  expect(close.preventDefault).toHaveBeenCalledOnce()
  expect(main.hide).toHaveBeenCalledOnce()
  retainMainWindowForStudio(close, main, 101, true)
  expect(close.preventDefault).toHaveBeenCalledOnce()
})
