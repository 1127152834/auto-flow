import { app, BrowserWindow, ipcMain } from 'electron'
import { join } from 'node:path'
import { SidecarSupervisor } from './sidecar/supervisor'
import { resolvePackagedSidecarPath, resolvePlatformPaths } from './platform/paths'

let mainWindow: BrowserWindow | undefined
let supervisor: SidecarSupervisor | undefined

async function createWindow(): Promise<void> {
  supervisor = new SidecarSupervisor({
    instanceId: `${process.pid}-${Date.now()}`,
    dataDir: app.getPath('userData'),
    production: app.isPackaged,
    sidecarPath: app.isPackaged ? resolvePackagedSidecarPath(process.resourcesPath, process.platform) : undefined,
  })
  void supervisor.start().catch(() => undefined)
  mainWindow = new BrowserWindow({ webPreferences: { preload: join(__dirname, '../preload/index.js'), contextIsolation: true, sandbox: true, nodeIntegration: false } })
  if (process.env.ELECTRON_RENDERER_URL) await mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL)
  else await mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
}

app.whenReady().then(() => {
  ipcMain.handle('autoflow:sidecar-status', () => supervisor?.getStatus() ?? { state: 'stopped' })
  ipcMain.handle('autoflow:sidecar-restart', () => supervisor?.restart() ?? Promise.resolve({ state: 'stopped' as const }))
  ipcMain.handle('autoflow:platform-paths', () => resolvePlatformPaths(app.getPath('userData')))
  void createWindow()
})
let isQuitting = false
app.on('before-quit', event => {
  if (isQuitting) return
  event.preventDefault()
  isQuitting = true
  void (supervisor?.stop() ?? Promise.resolve()).finally(() => app.quit())
})
