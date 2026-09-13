import { BrowserWindow } from 'electron'
import type { UiPreferences } from '../../shared/settings'

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

/** Owns the single independent Studio window. */
export class StudioWindowController {
  private window: BrowserWindow | undefined

  constructor(private readonly options: StudioWindowOptions) {}

  async open(event: DesktopIpcEvent): Promise<void> {
    if (!isWindowMainFrame(event, this.options.mainSenderId())) throw new Error('此窗口不能打开工作流工作台')
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
    window.once('closed', () => { if (this.window === window) this.window = undefined })
    window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
    window.webContents.on('will-navigate', event => event.preventDefault())
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

  applyPreferences(preferences: UiPreferences): void {
    if (!this.window || this.window.isDestroyed()) return
    this.window.webContents.setZoomFactor(preferences.zoom / 100)
    this.window.webContents.send('autoflow:preferences-changed', preferences)
  }
}
