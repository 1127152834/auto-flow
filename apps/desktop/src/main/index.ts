import { app, BrowserWindow, clipboard, ipcMain, shell } from 'electron'
import { join } from 'node:path'
import { SidecarSupervisor } from './sidecar/supervisor'
import { resolvePackagedSidecarPath, resolvePlatformPaths } from './platform/paths'
import { createCopyProxyCredentialsHandler } from './ipc/proxy-credentials'
import { createRevealKernelHandler } from './ipc/kernel-paths'

let mainWindow: BrowserWindow | undefined
let supervisor: SidecarSupervisor | undefined

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({ width: 1440, height: 1024, minWidth: 800, minHeight: 600, webPreferences: { preload: join(__dirname, '../preload/index.js'), contextIsolation: true, sandbox: true, nodeIntegration: false } })
  ipcMain.removeHandler('autoflow:copy-proxy-credentials')
  ipcMain.handle('autoflow:copy-proxy-credentials', createCopyProxyCredentialsHandler({
    allowedSenderId: mainWindow.webContents.id,
    getSidecarStatus: () => supervisor?.getHostStatus() ?? { state: 'stopped' },
    request: fetch,
    clipboard,
  }))
  ipcMain.removeHandler('autoflow:reveal-kernel')
  ipcMain.handle('autoflow:reveal-kernel', createRevealKernelHandler({
    allowedSenderId: mainWindow.webContents.id,
    getSidecarStatus: () => supervisor?.getHostStatus() ?? { state: 'stopped' },
    request: fetch,
    showItemInFolder: path => shell.showItemInFolder(path),
  }))
  mainWindow.on('closed', () => { mainWindow = undefined })
  if (process.env.ELECTRON_RENDERER_URL) await mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL)
  else await mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
}

app.whenReady().then(() => {
  supervisor = new SidecarSupervisor({
    instanceId: `${process.pid}-${Date.now()}`,
    dataDir: app.getPath('userData'),
    backendDirectory: join(__dirname, '../../../backend'),
    rendererOrigin: process.env.ELECTRON_RENDERER_URL ? new URL(process.env.ELECTRON_RENDERER_URL).origin : 'null',
    production: app.isPackaged,
    sidecarPath: app.isPackaged ? resolvePackagedSidecarPath(process.resourcesPath, process.platform) : undefined,
  })
  void supervisor.start().catch(() => undefined)

  ipcMain.handle('autoflow:sidecar-status', () => supervisor?.getStatus() ?? { state: 'stopped' })
  ipcMain.handle('autoflow:sidecar-restart', () => supervisor?.restart() ?? Promise.resolve({ state: 'stopped' as const }))
  ipcMain.handle('autoflow:platform-paths', () => resolvePlatformPaths(app.getPath('userData')))
  void createWindow()
})
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) void createWindow() })
let isQuitting = false
let stoppedForQuit = false
app.on('before-quit', event => {
  if (stoppedForQuit) return
  event.preventDefault()
  if (isQuitting) return
  isQuitting = true
  void (supervisor?.stop() ?? Promise.resolve()).finally(() => { stoppedForQuit = true; app.quit() })
})
