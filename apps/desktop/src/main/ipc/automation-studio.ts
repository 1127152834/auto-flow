import {randomUUID} from 'node:crypto'
import type {StudioLeaveRequest, StudioOpenContext} from '../../shared/automation-studio'
import { BrowserWindow, dialog } from 'electron'
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
  workspacePartition?():string
  onInvalidated?(): void
  onClosed?(): void
}

/** Owns the single independent Studio window. */
export class StudioWindowController {
  private window: BrowserWindow | undefined
  private ready=false
  private everReady=false
  private pendingLeave: {id:string;promise:Promise<boolean>;resolve:(allowed:boolean)=>void}|undefined
  private closeResult: ((closed: boolean) => void) | undefined
  private opening: { key: string; promise: Promise<void> } | undefined

  constructor(private readonly options: StudioWindowOptions) {}

  async open(event: DesktopIpcEvent, rawContext?: unknown): Promise<void> {
    if (!isWindowMainFrame(event, this.options.mainSenderId())) throw new Error('此窗口不能打开工作流工作台')
    const context = normalizeContext(rawContext)
    const key = contextKey(context)
    if (this.opening) {
      if (this.opening.key !== key) throw new Error('工作流工作台正在切换，请稍后重试')
      return this.opening.promise
    }
    const promise = this.openContext(context)
    this.opening = { key, promise }
    try { await promise } finally { this.opening = undefined }
  }

  private async openContext(context: StudioOpenContext): Promise<void> {
    if (this.window && !this.window.isDestroyed() && this.contextKey !== contextKey(context)) {
      const source = this.window
      if (!await this.prepareLeave('workspace')) throw new Error('工作流工作台仍有未保存修改')
      if (!source.isDestroyed()) source.destroy()
    }
    return this.openWindow(context)
  }

  private contextKey = ''

  private async openWindow(context: StudioOpenContext = {}):Promise<void> {
    if (this.window && !this.window.isDestroyed()) {
      if (this.window.isMinimized()) this.window.restore()
      this.window.show(); this.window.focus()
      return
    }
    this.contextKey = contextKey(context)
    const window = new BrowserWindow({
      title: '工作流工作台 · AutoFlow', width: 1440, height: 1024, minWidth: 800, minHeight: 600,
      backgroundColor: '#f1eee7', show: false,
      webPreferences: { ...(this.options.workspacePartition?{partition:this.options.workspacePartition()}:{}), preload: this.options.preloadPath, contextIsolation: true, sandbox: true, nodeIntegration: false },
    })
    this.window = window
    this.ready=false;this.everReady=false
    window.on('close',event=>{
      if(!this.everReady)return
      event.preventDefault()
      void this.prepareLeave('close').then(allowed=>{if(allowed&&!window.isDestroyed())window.destroy()})
    })
    window.webContents.on('render-process-gone',()=>{this.ready=false;this.finishLeave(false);this.options.onInvalidated?.()})
    window.webContents.on('did-start-loading',()=>{this.ready=false;this.finishLeave(false);this.options.onInvalidated?.()})
    window.once('closed', () => {
      this.options.onInvalidated?.()
      if (this.window === window) this.window = undefined
      this.finishLeave(false)
      this.closeResult?.(true); this.closeResult = undefined
      this.options.onClosed?.()
    })
    window.webContents.on('will-prevent-unload', event => {
      const discard = dialog.showMessageBoxSync(window, {type:'warning',title:'工作流尚未保存',message:'关闭将放弃当前未保存的编辑。',detail:'需要保存时，请选择继续编辑，再使用保存按钮。',buttons:['放弃并关闭','继续编辑'],defaultId:1,cancelId:1}) === 0
      if (discard) event.preventDefault()
      else {this.closeResult?.(false);this.closeResult = undefined}
    })
    window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
    window.webContents.on('will-navigate', event => event.preventDefault())
    window.webContents.on('did-finish-load', () => this.applyPreferences(this.options.preferences()))
    try {
      if (this.options.rendererUrl) {
        const url = new URL(this.options.rendererUrl)
        url.searchParams.set('view', 'automation-studio')
        applyContext(url.searchParams, context)
        await window.loadURL(url.toString())
      } else await window.loadFile(this.options.rendererFile, { query: { view: 'automation-studio', ...context } })
      if (!window.isDestroyed()) {
        window.setTitle('工作流工作台 · AutoFlow'); window.show(); window.focus()
      }
    } catch {
      if (!window.isDestroyed()) window.destroy()
      throw new Error('无法打开工作流工作台，请重试')
    }
  }

  isStudioSender(event:DesktopIpcEvent):boolean {
    return isWindowMainFrame(event,this.window?.webContents.id)
  }
  senderId(): number | undefined {
    return this.window && !this.window.isDestroyed() ? this.window.webContents.id : undefined
  }
  sendHotkey(actionId: string): void {
    if (this.ready && !this.pendingLeave && this.window && !this.window.isDestroyed()) {
      this.window.webContents.send('autoflow:studio-hotkey', actionId)
    }
  }
  registerLeaveReady(event:DesktopIpcEvent):void {
    if(!this.isStudioSender(event))throw new Error('此窗口不能注册工作台离开协调')
    this.ready=true;this.everReady=true
  }
  completeLeave(event:DesktopIpcEvent,value:unknown):void {
    if(!this.isStudioSender(event))throw new Error('此窗口不能确认工作台离开')
    if(!value||typeof value!=='object'||!('id' in value)||!('allowed' in value)||typeof value.allowed!=='boolean'||value.id!==this.pendingLeave?.id)throw new Error('离开确认已过期或格式无效')
    this.finishLeave(value.allowed)
  }
  private finishLeave(allowed:boolean):void {
    const pending=this.pendingLeave;this.pendingLeave=undefined;pending?.resolve(allowed)
  }
  async prepareLeave(reason:StudioLeaveRequest['reason']):Promise<boolean> {
    if(!this.window||this.window.isDestroyed())return true
    if(this.pendingLeave)return this.pendingLeave.promise
    if(!this.ready)return false
    const id=randomUUID()
    let resolve!:(allowed:boolean)=>void
    const promise=new Promise<boolean>(done=>{resolve=done})
    this.pendingLeave={id,promise,resolve}
    if (reason !== 'restart') {
      if (this.window.isMinimized()) this.window.restore()
      this.window.show()
      this.window.focus()
    }
    this.window.webContents.send('autoflow:studio-prepare-leave',{id,reason})
    return promise
  }

  async closeForQuit(): Promise<boolean> {
    if (!this.window || this.window.isDestroyed()) return true
    if(this.everReady){
      const window=this.window
      if(!await this.prepareLeave('quit'))return false
      if(!window.isDestroyed())window.destroy()
      return true
    }
    return new Promise(resolve => { this.closeResult = resolve; this.window!.close() })
  }

  async finishWorkspaceTransition(changed:boolean):Promise<void> {
    if(!this.window||this.window.isDestroyed())return
    if(changed){this.window.destroy();await this.openWindow()}
    else this.window.webContents.send('autoflow:studio-transition-end')
  }

  applyPreferences(preferences: UiPreferences): void {
    if (!this.window || this.window.isDestroyed()) return
    this.window.webContents.setZoomFactor(preferences.zoom / 100)
    this.window.webContents.send('autoflow:preferences-changed', preferences)
  }
}

function normalizeContext(value: unknown): StudioOpenContext {
  if (value === undefined) return {}
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('工作台上下文无效')
  const source = value as Record<string, unknown>
  const result: StudioOpenContext = {}
  for (const key of ['workspaceKey', 'instanceId', 'projectId', 'workflowId'] as const) {
    const entry = source[key]
    if (entry === undefined) continue
    if (typeof entry !== 'string' || entry.trim().length === 0 || entry.length > 200) throw new Error('工作台上下文无效')
    result[key] = entry
  }
  return result
}

function contextKey(context: StudioOpenContext): string {
  return JSON.stringify([context.workspaceKey ?? '', context.instanceId ?? '', context.projectId ?? '', context.workflowId ?? ''])
}

function applyContext(params: URLSearchParams, context: StudioOpenContext): void {
  for (const [key, value] of Object.entries(context)) if (value) params.set(key, value)
}

/** Keep the one project interaction owner alive while the independent Studio remains open. */
export function retainMainWindowForStudio(event: { preventDefault(): void }, window: { hide(): void }, studioSenderId: number | undefined, quitting: boolean): void {
  if (studioSenderId === undefined || quitting) return
  event.preventDefault()
  window.hide()
}
