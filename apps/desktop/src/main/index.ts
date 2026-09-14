import { app, BrowserWindow, clipboard, dialog, ipcMain, shell } from 'electron'
import { join } from 'node:path'
import { SidecarSupervisor } from './sidecar/supervisor'
import { resolvePackagedSidecarPath, resolvePlatformPaths } from './platform/paths'
import { createCopyProxyCredentialsHandler } from './ipc/proxy-credentials'
import { createOpenExternalLinkHandler } from './ipc/external-links'
import { createRevealKernelHandler } from './ipc/kernel-paths'
import { isWindowMainFrame, StudioWindowController, type DesktopIpcEvent } from './ipc/automation-studio'
import { protectSettingsHandler } from './ipc/settings'
import { DesktopSettingsStore, SettingsError } from './settings/store'
import { ProjectFilesController } from './project-files/controller'
import { SettingsController } from './settings/controller'
import type { UiPreferences } from '../shared/settings'

let mainWindow: BrowserWindow | undefined
let settings: SettingsController | undefined
const studio = new StudioWindowController({
  mainSenderId: () => mainWindow?.webContents.id,
  preferences: () => settings?.getPreferences() ?? { zoom: 100, motion: 'system' },
  preloadPath: join(__dirname, '../preload/index.js'),
  rendererFile: join(__dirname, '../renderer/studio.html'),
  rendererUrl: process.env.ELECTRON_RENDERER_URL ? new URL('studio.html', process.env.ELECTRON_RENDERER_URL).toString() : undefined,
})

function requireRuntimeSender(event: DesktopIpcEvent): void {
  if (!isWindowMainFrame(event, mainWindow?.webContents.id)) throw new Error('此窗口不能访问本地服务')
}

function publishRuntimeContext(): void {
  if (!settings) return
  const context = settings.getRuntimeContext()
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('autoflow:runtime-context-changed', context)
}

function applyPreferences(preferences: UiPreferences): void {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.setZoomFactor(preferences.zoom / 100)
    mainWindow.webContents.send('autoflow:preferences-changed', preferences)
  }
  studio.applyPreferences(preferences)
}

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({ width: 1440, height: 1024, minWidth: 800, minHeight: 600, webPreferences: { preload: join(__dirname, '../preload/index.js'), contextIsolation: true, sandbox: true, nodeIntegration: false } })
  const projectFiles = new ProjectFilesController({
    allowedSenderId: mainWindow.webContents.id,
    getHostStatus: () => settings?.getHostStatus() ?? { state: 'stopped' },
    showOpenDialog: options => dialog.showOpenDialog(mainWindow!, options as Electron.OpenDialogOptions),
    showSaveDialog: options => dialog.showSaveDialog(mainWindow!, options as Electron.SaveDialogOptions),
  })
  ipcMain.removeHandler('autoflow:project-files:context')
  ipcMain.handle('autoflow:project-files:context', event => projectFiles.getProjectFileContext(event))
  ipcMain.removeHandler('autoflow:project-files:choose-excel-input')
  ipcMain.handle('autoflow:project-files:choose-excel-input', (event, projectId: unknown) => projectFiles.chooseExcelInput(event, projectId))
  ipcMain.removeHandler('autoflow:project-files:choose-xlsx-output')
  ipcMain.handle('autoflow:project-files:choose-xlsx-output', (event, projectId: unknown, suggestedName: unknown) => projectFiles.chooseXlsxOutput(event, projectId, suggestedName))
  ipcMain.removeHandler('autoflow:copy-proxy-credentials')
  ipcMain.handle('autoflow:copy-proxy-credentials', createCopyProxyCredentialsHandler({
    allowedSenderId: mainWindow.webContents.id,
    getSidecarStatus: () => settings?.getHostStatus() ?? { state: 'stopped' },
    request: fetch,
    clipboard,
  }))
  ipcMain.removeHandler('autoflow:open-external-link')
  ipcMain.handle('autoflow:open-external-link', createOpenExternalLinkHandler({ allowedSenderId: mainWindow.webContents.id, openExternal: url => shell.openExternal(url) }))
  ipcMain.removeHandler('autoflow:reveal-kernel')
  ipcMain.handle('autoflow:reveal-kernel', createRevealKernelHandler({
    allowedSenderId: mainWindow.webContents.id,
    getSidecarStatus: () => settings?.getHostStatus() ?? { state: 'stopped' },
    request: fetch,
    showItemInFolder: path => shell.showItemInFolder(path),
  }))
  const actions: Record<string, (...args: unknown[]) => Promise<unknown>> = {
    'get': () => settings!.snapshot(),
    'preferences': value => settings!.setPreferences(value),
    'choose-workspace': source => settings!.chooseWorkspace(source),
    'confirm-workspace': async id => {
      try { return await settings!.confirmWorkspace(id) } finally { publishRuntimeContext() }
    },
    'open-directory': directory => settings!.openDirectory(directory),
    'preview-diagnostics': includeLogs => settings!.previewDiagnostics(includeLogs),
    'save-diagnostics': id => settings!.saveDiagnostics(id),
    'quit': async () => { setTimeout(() => app.quit(), 0); return { quitting: true } },
  }
  for (const [name, action] of Object.entries(actions)) {
    const channel = `autoflow:settings:${name}`
    ipcMain.removeHandler(channel)
    ipcMain.handle(channel, protectSettingsHandler(mainWindow.webContents.id, action))
  }
  ipcMain.removeHandler('autoflow:sidecar-restart')
  ipcMain.handle('autoflow:sidecar-restart', async event => {
    requireRuntimeSender(event)
    try { return await settings!.restart() } catch (error) { throw new Error(error instanceof SettingsError ? error.message : '本地服务重启失败，请重试') } finally { publishRuntimeContext() }
  })
  mainWindow.webContents.on('did-finish-load', () => { if (settings) applyPreferences(settings.getPreferences()) })
  mainWindow.on('closed', () => { settings?.invalidateChoices(); mainWindow = undefined })
  if (process.env.ELECTRON_RENDERER_URL) await mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL)
  else await mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
}

const primaryInstance = app.requestSingleInstanceLock()
if (!primaryInstance) app.quit()
app.on('second-instance', () => { if (mainWindow) { if (mainWindow.isMinimized()) mainWindow.restore(); mainWindow.focus() } else if (app.isReady()) void createWindow() })
app.whenReady().then(async () => {
  if (!primaryInstance) return
  settings = new SettingsController({
    store: new DesktopSettingsStore(app.getPath('userData')),
    createSidecar: dataDir => new SidecarSupervisor({
      instanceId: `${process.pid}-${Date.now()}`,
      dataDir,
      backendDirectory: join(__dirname, '../../../backend'),
      rendererOrigin: process.env.ELECTRON_RENDERER_URL ? new URL(process.env.ELECTRON_RENDERER_URL).origin : 'null',
      production: app.isPackaged,
      sidecarPath: app.isPackaged ? resolvePackagedSidecarPath(process.resourcesPath, process.platform) : undefined,
    }),
    runtime: { appVersion: app.getVersion(), electronVersion: process.versions.electron, chromeVersion: process.versions.chrome, nodeVersion: process.versions.node, platform: process.platform === 'darwin' ? 'macos' : process.platform === 'win32' ? 'windows' : 'linux', arch: process.arch },
    selectDirectory: async () => {
      const options = { title: '选择 AutoFlow 工作区', defaultPath: settings?.getWorkspacePath(), properties: ['openDirectory', 'createDirectory'] as ('openDirectory' | 'createDirectory')[] }
      const result = mainWindow ? await dialog.showOpenDialog(mainWindow, options) : await dialog.showOpenDialog(options)
      return result.canceled ? null : result.filePaths[0] ?? null
    },
    selectSavePath: async filename => {
      const options = { title: '保存诊断文件', defaultPath: filename, filters: [{ name: 'JSON 诊断文件', extensions: ['json'] }] }
      const result = mainWindow ? await dialog.showSaveDialog(mainWindow, options) : await dialog.showSaveDialog(options)
      return result.canceled ? null : result.filePath ?? null
    },
    openPath: path => shell.openPath(path),
    applyPreferences,
  })
  void settings.start().catch(() => undefined)

  ipcMain.handle('autoflow:open-automation-studio', event => studio.open(event))
  ipcMain.handle('autoflow:runtime-context', event => { requireRuntimeSender(event); return settings!.getRuntimeContext() })
  ipcMain.handle('autoflow:sidecar-status', event => { requireRuntimeSender(event); return settings!.getPublicStatus() })
  ipcMain.handle('autoflow:platform-paths', event => {
    if (!isWindowMainFrame(event, mainWindow?.webContents.id)) throw new Error('此窗口不能读取本机目录')
    return resolvePlatformPaths(app.getPath('userData'))
  })
  await createWindow()
}).catch(() => { dialog.showErrorBox('AutoFlow 无法启动', '无法读取本机应用目录或设置，请检查目录权限后重新启动。现有数据未删除。'); app.quit() })
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
app.on('activate', () => { if (!mainWindow || mainWindow.isDestroyed()) void createWindow() })
let isQuitting = false
let stoppedForQuit = false
app.on('before-quit', event => {
  if (stoppedForQuit) return
  event.preventDefault()
  if (isQuitting) return
  isQuitting = true
  void (async () => {
    try {
      if (!await studio.closeForQuit()) { isQuitting = false; return }
      await settings?.shutdown()
      stoppedForQuit = true
      app.quit()
    } catch {
      isQuitting = false
      dialog.showErrorBox('暂未退出 AutoFlow', '本地服务未能停止，请重试退出。')
    }
  })()
})
