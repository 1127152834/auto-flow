import {createHash} from 'node:crypto'
import { execFile } from 'node:child_process'
import { realpathSync } from 'node:fs'
import { app, BrowserWindow, clipboard, dialog, globalShortcut, ipcMain, nativeImage, Notification, shell } from 'electron'
import { join } from 'node:path'
import { SidecarSupervisor } from './sidecar/supervisor'
import { resolvePackagedSidecarPath, resolvePlatformPaths } from './platform/paths'
import { createCopyProxyCredentialsHandler } from './ipc/proxy-credentials'
import { createOpenExternalLinkHandler } from './ipc/external-links'
import { createConnectGoogleSheetsHandler } from './google-desktop'
import { createRevealKernelHandler } from './ipc/kernel-paths'
import { createStudioPlatformActionHandler } from './ipc/studio-platform'
import { createSystemControlActions } from './platform/system-control'
import { isWindowMainFrame, StudioWindowController, type DesktopIpcEvent } from './ipc/automation-studio'
import { protectSettingsHandler } from './ipc/settings'
import { DesktopSettingsStore, SettingsError } from './settings/store'
import { ProjectFilesController } from './project-files/controller'
import { SettingsController } from './settings/controller'
import type { UiPreferences } from '../shared/settings'
import { ScheduledHotkeyController } from './scheduled-hotkeys'

let mainWindow: BrowserWindow | undefined
let settings: SettingsController | undefined
let scheduledHotkeys: ScheduledHotkeyController | undefined

function runSystemCommand(file:string,args:string[]):Promise<string>{
  return new Promise(resolve=>execFile(file,args,{windowsHide:true},error=>resolve(error?.message??'')))
}

const systemControl=createSystemControlActions(process.platform,runSystemCommand)
/**
 * Development-only: the exact config file an automated run hands to the Google
 * authorization handler instead of a native picker. A packaged build always
 * reads `undefined` and keeps the real dialog.
 */
const qaGoogleConfigPath = !app.isPackaged ? process.env.AUTOFLOW_QA_GOOGLE_CONFIG : undefined
/**
 * Development-only: the fixture files an automated run hands to the project
 * file controller instead of the native pickers. A packaged build always reads
 * `undefined`, and the real controller still validates window, main frame,
 * workspace, project, purpose and the file itself.
 */
const qaExcelInput = !app.isPackaged ? process.env.AUTOFLOW_QA_EXCEL_INPUT : undefined
const qaXlsxOutputDir = !app.isPackaged ? process.env.AUTOFLOW_QA_XLSX_OUTPUT : undefined
const studio = new StudioWindowController({
  mainSenderId: () => mainWindow?.webContents.id,
  workspacePartition:()=>{
    const path=settings?.getRuntimeContext().workspaceKey
    return `persist:studio-${createHash('sha256').update(path?realpathSync(path):'uninitialized').digest('hex')}`
  },
  preferences: () => settings?.getPreferences() ?? { zoom: 100, motion: 'system' },
  preloadPath: join(__dirname, '../preload/index.js'),
  rendererFile: join(__dirname, '../renderer/studio.html'),
  rendererUrl: process.env.ELECTRON_RENDERER_URL ? new URL('studio.html', process.env.ELECTRON_RENDERER_URL).toString() : undefined,
})

function requireRuntimeSender(event: DesktopIpcEvent): void {
  if (!isWindowMainFrame(event, mainWindow?.webContents.id)&&!studio.isStudioSender(event)) throw new Error('此窗口不能访问本地服务')
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
    showOpenDialog: qaExcelInput
      ? async () => ({ canceled: false, filePaths: [String(qaExcelInput)] })
      : options => dialog.showOpenDialog(mainWindow!, options as Electron.OpenDialogOptions),
    showSaveDialog: qaXlsxOutputDir
      ? async options => ({ canceled: false, filePath: join(qaXlsxOutputDir, String((options as { defaultPath?: string }).defaultPath ?? '导出.xlsx')) })
      : options => dialog.showSaveDialog(mainWindow!, options as Electron.SaveDialogOptions),
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
  ipcMain.removeHandler('autoflow:google-sheets:connect')
  ipcMain.handle('autoflow:google-sheets:connect', createConnectGoogleSheetsHandler({
    allowedSenderId: mainWindow.webContents.id,
    getSidecarStatus: () => settings?.getHostStatus() ?? { state: 'stopped' },
    // Same development-only switch class as AUTOFLOW_QA_SIDECAR_MODULE: an
    // automated run cannot drive the native picker, so it hands the harness's
    // own fixture path in instead. A packaged build always uses the dialog.
    chooseConfigFile: qaGoogleConfigPath
      ? async () => qaGoogleConfigPath
      : async () => {
          const picked = await dialog.showOpenDialog(mainWindow!, {
            title: '选择 Google 连接配置',
            properties: ['openFile'],
            filters: [{ name: 'Google JSON 配置', extensions: ['json'] }],
          })
          if (picked.canceled || !picked.filePaths.length) return null
          if (picked.filePaths.length !== 1 || !picked.filePaths[0]?.toLowerCase().endsWith('.json')) throw new Error('请选择一个 JSON 配置文件。')
          return picked.filePaths[0]
        },
    openExternal: url => shell.openExternal(url),
    request: fetch,
  }))
  ipcMain.removeHandler('autoflow:reveal-kernel')
  ipcMain.handle('autoflow:reveal-kernel', createRevealKernelHandler({
    allowedSenderId: mainWindow.webContents.id,
    getSidecarStatus: () => settings?.getHostStatus() ?? { state: 'stopped' },
    request: fetch,
    showItemInFolder: path => shell.showItemInFolder(path),
  }))
  ipcMain.removeHandler('autoflow:studio-platform-action')
  ipcMain.handle('autoflow:studio-platform-action',createStudioPlatformActionHandler({
    allowed:event=>studio.isStudioSender(event),
    writeText:value=>clipboard.writeText(value),
    readText:()=>clipboard.readText(),
    writeImage:path=>{const image=nativeImage.createFromPath(path);if(image.isEmpty())return false;clipboard.writeImage(image);return true},
    beep:()=>shell.beep(),
    notify:request=>{const notification=new Notification({title:request.title,body:request.message,silent:!request.playSound});notification.show();setTimeout(()=>notification.close(),request.duration*1000)},
    openPath:path=>shell.openPath(path),
    systemControl:request=>systemControl.execute(request),
    lockScreen:()=>systemControl.lock(),
  }))
  const actions: Record<string, (...args: unknown[]) => Promise<unknown>> = {
    'get': () => settings!.snapshot(),
    'preferences': value => settings!.setPreferences(value),
    'choose-workspace': source => settings!.chooseWorkspace(source),
    'confirm-workspace': async id => {
      const previous=settings!.getRuntimeContext().workspaceKey
      if(!await studio.prepareLeave('workspace'))throw new SettingsError('STUDIO_LEAVE_DECLINED', '工作台未确认离开，已保留当前工作区')
      try {return await settings!.confirmWorkspace(id)}
      finally{
        publishRuntimeContext()
        await studio.finishWorkspaceTransition(settings!.getRuntimeContext().workspaceKey!==previous)
      }
    },
    'open-directory': directory => settings!.openDirectory(directory),
    'preview-diagnostics': includeLogs => settings!.previewDiagnostics(includeLogs),
    'save-diagnostics': id => settings!.saveDiagnostics(id),
    'save-android-diagnostic': id => settings!.saveAndroidDiagnostic(id),
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
    // A dead sidecar cannot release the stale renderer resource. The new
    // sidecar reconciles persisted active runs as interrupted during startup.
    if(settings!.getStatus().state==='ready'&&!await studio.prepareLeave('restart'))throw new Error('请先结束工作台的活跃会话，再重启服务')
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
      developmentModule: !app.isPackaged && process.env.AUTOFLOW_QA_SIDECAR_MODULE
        ? process.env.AUTOFLOW_QA_SIDECAR_MODULE
        : !app.isPackaged && process.env.AUTOFLOW_PM4_QA === '1'
          ? 'tests.qa.pm4_sidecar'
          : undefined,
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
  scheduledHotkeys = new ScheduledHotkeyController({
    shortcuts: globalShortcut,
    getSidecarStatus: () => settings?.getPublicStatus() ?? { state: 'stopped' },
  })
  scheduledHotkeys.start()

  ipcMain.handle('autoflow:open-automation-studio', event => studio.open(event))
  ipcMain.handle('autoflow:studio-leave-ready',event=>studio.registerLeaveReady(event))
  ipcMain.handle('autoflow:studio-leave-result',(event,result:unknown)=>studio.completeLeave(event,result))
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
      scheduledHotkeys?.stop()
      await settings?.shutdown()
      stoppedForQuit = true
      app.quit()
    } catch {
      isQuitting = false
      scheduledHotkeys?.start()
      dialog.showErrorBox('暂未退出 AutoFlow', '本地服务未能停止，请重试退出。')
    }
  })()
})
