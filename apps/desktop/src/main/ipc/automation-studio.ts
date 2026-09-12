import { BrowserWindow, Menu, type MenuItem } from 'electron'
import { randomUUID } from 'node:crypto'
import type { StudioLeaveReason } from '../../shared/automation-studio'
import type { UiPreferences } from '../../shared/settings'
import type { DesktopRuntimeContext } from '../../shared/runtime'

export type DesktopIpcEvent = { sender: { id: number; mainFrame: unknown }; senderFrame: unknown }

export function isWindowMainFrame(event: DesktopIpcEvent, senderId: number | undefined): boolean {
  return senderId !== undefined && event.sender.id === senderId && Boolean(event.senderFrame) && event.senderFrame === event.sender.mainFrame
}

type StudioWindowOptions = {
  mainSenderId(): number | undefined
  preferences(): UiPreferences
  preloadPath: string
  rendererFile: string
  rendererUrl?: string
}

/** Owns the one Studio window and serializes its destructive desktop transitions. */
export class StudioWindowController {
  private window: BrowserWindow | undefined
  private ready = false
  private allowedClose: BrowserWindow | undefined
  private pending: { id: string; resolve(approved: boolean): void } | undefined
  private transitioning = false
  private reloadMenuItems = new Map<MenuItem, boolean>()

  constructor(private readonly options: StudioWindowOptions) {}

  isSender(event: DesktopIpcEvent): boolean {
    return this.window !== undefined && !this.window.isDestroyed() && isWindowMainFrame(event, this.window.webContents.id)
  }

  isTransitioning(): boolean { return this.transitioning || Boolean(this.pending) }

  async open(event: DesktopIpcEvent): Promise<void> {
    if (!isWindowMainFrame(event, this.options.mainSenderId())) throw new Error('此窗口不能打开工作流工作台')
    if (this.transitioning) throw new Error('工作区正在切换或应用正在退出，请稍候')
    if (this.window && !this.window.isDestroyed()) {
      if (this.window.isMinimized()) this.window.restore()
      this.window.show(); this.window.focus()
      return
    }
    const window = new BrowserWindow({
      title: '工作流工作台 · AutoFlow', width: 1440, height: 1024, minWidth: 800, minHeight: 600,
      backgroundColor: '#f1eee7', show: false,
      webPreferences: { preload: this.options.preloadPath, contextIsolation: true, sandbox: true, nodeIntegration: false },
    })
    this.window = window
    this.ready = false
    window.once('closed', () => {
      if (this.window !== window) return
      this.window = undefined; this.ready = false; this.allowedClose = undefined
      this.pending?.resolve(false); this.pending = undefined
      this.restoreReloadMenu()
    })
    window.on('focus', () => this.blockReloadMenu())
    window.on('close', event => {
      if (this.allowedClose === window) return
      event.preventDefault()
      void this.close()
    })
    window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
    window.webContents.on('will-navigate', event => event.preventDefault())
    window.webContents.on('before-input-event', (event, input) => {
      if (input.key === 'F5' || ((input.control || input.meta) && input.key.toLowerCase() === 'r')) event.preventDefault()
    })
    window.webContents.on('render-process-gone', () => {
      this.ready = false
      this.pending?.resolve(false); this.pending = undefined
      this.finishTransition()
    })
    window.webContents.on('did-finish-load', () => this.applyPreferences(this.options.preferences()))
    try {
      if (this.options.rendererUrl) {
        const url = new URL(this.options.rendererUrl)
        url.searchParams.set('view', 'automation-studio')
        await window.loadURL(url.toString())
      } else await window.loadFile(this.options.rendererFile, { query: { view: 'automation-studio' } })
      if (!window.isDestroyed()) {
        window.setTitle('工作流工作台 · AutoFlow'); window.show(); window.focus()
      }
    } catch {
      if (!window.isDestroyed()) window.destroy()
      throw new Error('无法打开工作流工作台，请重试')
    }
  }

  markReady(event: DesktopIpcEvent, ready: unknown): void {
    if (!this.isSender(event) || typeof ready !== 'boolean') throw new Error('无效的工作台状态')
    this.ready = ready
  }

  reply(event: DesktopIpcEvent, id: unknown, approved: unknown): void {
    if (!this.isSender(event) || typeof id !== 'string' || typeof approved !== 'boolean') throw new Error('无效的工作台离开确认')
    if (!this.pending || this.pending.id !== id) return
    const pending = this.pending
    this.pending = undefined
    pending.resolve(approved)
  }

  async prepareLeave(reason: StudioLeaveReason): Promise<boolean> {
    // On Windows, closing the last Studio window can synchronously trigger application quit.
    if (this.isTransitioning() && !(reason === 'quit' && !this.window && !this.pending)) return false
    if (this.window && !this.window.isDestroyed() && this.ready) {
      // A quit/workspace request can originate in the main window while Studio is minimized.
      if (this.window.isMinimized()) this.window.restore()
      this.window.show(); this.window.focus()
      const approved = await new Promise<boolean>(resolve => {
        const id = randomUUID()
        this.pending = { id, resolve }
        try { this.window!.webContents.send('autoflow:studio-prepare-leave', { id, reason }) }
        catch { this.pending = undefined; resolve(false) }
      })
      if (!approved) { this.finishTransition(); return false }
    }
    this.transitioning = true
    this.sendTransition(true)
    return true
  }

  finishTransition(): void {
    this.transitioning = false
    this.sendTransition(false)
  }

  permitClose(): void { this.allowedClose = this.window }

  restoreReloadMenu(): void {
    for (const [item, enabled] of this.reloadMenuItems) item.enabled = enabled
    this.reloadMenuItems.clear()
  }

  private blockReloadMenu(): void {
    const visit = (items: MenuItem[]) => {
      for (const item of items) {
        if (item.role?.toLowerCase() === 'reload' || item.role?.toLowerCase() === 'forcereload') {
          if (!this.reloadMenuItems.has(item)) this.reloadMenuItems.set(item, item.enabled)
          item.enabled = false
        }
        if (item.submenu) visit(item.submenu.items)
      }
    }
    const menu = Menu.getApplicationMenu()
    if (menu) visit(menu.items)
  }

  notifyRuntime(context: DesktopRuntimeContext): void {
    if (this.window && !this.window.isDestroyed()) this.window.webContents.send('autoflow:runtime-context-changed', context)
  }

  applyPreferences(preferences: UiPreferences): void {
    if (!this.window || this.window.isDestroyed()) return
    this.window.webContents.setZoomFactor(preferences.zoom / 100)
    this.window.webContents.send('autoflow:preferences-changed', preferences)
  }

  private sendTransition(locked: boolean): void {
    if (this.window && !this.window.isDestroyed()) this.window.webContents.send('autoflow:studio-transition', locked)
  }

  private async close(): Promise<void> {
    if (!await this.prepareLeave('close')) return
    try { this.permitClose(); this.window?.close() } finally { this.finishTransition() }
  }
}
