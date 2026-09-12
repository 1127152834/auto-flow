import { BrowserWindow, type IpcMainInvokeEvent } from 'electron'

let studioWindow: BrowserWindow | undefined

export function createOpenAutomationStudioHandler(allowedSenderId: number) {
  return async (event: Pick<IpcMainInvokeEvent, 'sender' | 'senderFrame'>): Promise<void> => {
    if (event.sender.id !== allowedSenderId || !event.senderFrame || event.senderFrame !== event.sender.mainFrame) {
      throw new Error('此窗口不能打开工作流工作台')
    }
    if (studioWindow && !studioWindow.isDestroyed()) {
      if (studioWindow.isMinimized()) studioWindow.restore()
      studioWindow.show()
      studioWindow.focus()
      return
    }

    const window = new BrowserWindow({
      title: '工作流工作台 · AutoFlow',
      width: 1440,
      height: 1024,
      minWidth: 800,
      minHeight: 600,
      backgroundColor: '#f1eee7',
      show: false,
      webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false },
    })
    studioWindow = window
    window.once('closed', () => { if (studioWindow === window) studioWindow = undefined })
    window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
    window.webContents.on('will-navigate', event => event.preventDefault())
    try {
      await window.loadURL('about:blank')
      if (!window.isDestroyed()) {
        window.setTitle('工作流工作台 · AutoFlow')
        window.show()
        window.focus()
      }
    } catch {
      if (!window.isDestroyed()) window.destroy()
      throw new Error('无法打开工作流工作台，请重试')
    }
  }
}
