import { randomUUID } from 'node:crypto'
import { mkdirSync, realpathSync, lstatSync, existsSync } from 'node:fs'
import { dirname, join, relative, sep } from 'node:path'
import type { SidecarStatus } from '../sidecar/supervisor'
import type { DesktopRuntimeContext } from '../../shared/runtime'
import type { DesktopSettingsSnapshot, DiagnosticPreview, SettingsDirectory, UiPreferences, WorkspaceChoice } from '../../shared/settings'
import { DesktopSettingsStore, ensureWritable, initializeWorkspace, inspectWorkspace, SettingsError, validatePreferences, writeAtomic, type StoredSettings } from './store'

type HostStatus = { state: 'ready'; baseUrl: string; hostToken: string; dataDir: string } | { state: 'stopped' }
export type ManagedSidecar = { start(): Promise<SidecarStatus>; stop(): Promise<void>; getStatus(): SidecarStatus; getHostStatus(): HostStatus }
type BackendRuntime = { apiVersion: string; backendVersion: string; pythonVersion: string; sqliteVersion: string; blockers: string[] }
type Runtime = Omit<DesktopSettingsSnapshot['runtime'], 'backendVersion' | 'pythonVersion' | 'sqliteVersion'>
export type SettingsControllerOptions = {
  store: DesktopSettingsStore
  createSidecar: (path: string) => ManagedSidecar
  runtime: Runtime
  selectDirectory(): Promise<string | null>
  selectSavePath(filename: string): Promise<string | null>
  openPath(path: string): Promise<string>
  applyPreferences(preferences: UiPreferences): void
  request?: typeof fetch
}
type RuntimeEvent = { timestamp: string; event: 'starting' | 'ready' | 'restarting' | 'switching' | 'recovered' | 'failed' | 'stopped' | 'exported'; code: string | null }
const BLOCKER_LABELS: Record<string, string> = {
  kernel_operation_active: '浏览器内核任务进行中', kernel_process_active: '浏览器内核仍在运行',
  proxy_sync_active: '代理同步进行中', proxy_operation_active: '代理任务进行中',
  profile_in_use: '浏览器配置正在使用', api_mutation_in_progress: '数据保存或资源操作进行中',
  api_mutations_paused: '服务正在准备切换',
  test_browser_process_active: '测试浏览器仍在运行',
  workflow_runs_active: '自动化运行记录尚未结束', workflow_worker_busy: '自动化正在执行',
  workflow_process_active: '自动化进程仍在运行',
  project_batches_active: '项目批次正在运行', project_lifecycle_pending: '项目归档或删除正在收尾',
  project_excel_operation_active: '项目导入导出进行中', project_data_status_batch_active: '批量状态更新进行中',
  project_manual_item_pending: '项目人工事项等待处理', project_sync_outcome_unknown: '项目同步结果尚未确认',
  android_management_active: '安卓设备管理进行中', android_console_active: '安卓控制台会话进行中',
}

export class SettingsController {
  private settings: StoredSettings
  private recovery: string | null
  private needsSelection: boolean
  private sidecar: ManagedSidecar | undefined
  private operation: DesktopSettingsSnapshot['operation'] = 'idle'
  private active: Promise<unknown> | undefined
  private choice: (WorkspaceChoice & { expires: number }) | undefined
  private preview: (DiagnosticPreview & { expires: number }) | undefined
  private events: RuntimeEvent[] = []
  private runtimeRequest: Promise<BackendRuntime | null> | undefined
  private quitting = false

  constructor(private readonly options: SettingsControllerOptions) {
    const loaded = options.store.load()
    this.settings = loaded.settings; this.recovery = loaded.recovery; this.needsSelection = loaded.needsSelection
    if (!this.needsSelection) {
      try { inspectWorkspace(this.settings.currentPath, false); ensureWritable(this.settings.currentPath) } catch {
        this.needsSelection = true; this.recovery = '已保存的工作区不可用，请重新选择工作区或退出应用'
      }
    }
  }

  getPreferences(): UiPreferences { return { ...this.settings.preferences } }
  getWorkspacePath(): string { return this.settings.currentPath }
  getStatus(): SidecarStatus { return this.sidecar?.getStatus() ?? { state: 'stopped' } }
  getPublicStatus(): SidecarStatus { return this.operation === 'switching' || this.operation === 'restarting' ? { state: 'starting' } : this.getStatus() }
  getRuntimeContext(): DesktopRuntimeContext {
    return { workspaceKey: this.settings.currentPath, sidecar: this.getPublicStatus(), preferences: this.getPreferences(), operation: this.operation }
  }
  getHostStatus(): HostStatus { return this.sidecar?.getHostStatus() ?? { state: 'stopped' } }
  invalidateChoices(): void { this.choice = undefined; this.preview = undefined }

  async start(): Promise<void> {
    if (this.needsSelection) return
    await this.exclusive('restarting', async () => { await this.launch(this.settings.currentPath) })
  }

  private async launch(path: string): Promise<void> {
    this.runtimeRequest = undefined
    this.record('starting')
    this.sidecar = this.options.createSidecar(path)
    const state = await this.sidecar.start()
    if (state.state !== 'ready') throw new SettingsError('SERVICE_START_FAILED', '本地服务未能就绪')
    this.record('ready')
  }

  private async backendRuntime(): Promise<BackendRuntime | null> {
    const status = this.sidecar?.getStatus()
    if (status?.state !== 'ready') return null
    if (this.runtimeRequest) return this.runtimeRequest
    const promise = (async () => {
      try {
        const response = await (this.options.request ?? fetch)(`${status.baseUrl}/api/v1/settings/runtime`, { headers: { 'x-autoflow-token': status.token }, signal: AbortSignal.timeout(3000) })
        if (!response.ok) return null
        const value = await response.json() as BackendRuntime
        if (!Array.isArray(value.blockers) || value.blockers.some(item => typeof item !== 'string')) return null
        return value
      } catch { return null }
    })()
    this.runtimeRequest = promise
    try { return await promise } finally { if (this.runtimeRequest === promise) this.runtimeRequest = undefined }
  }

  async snapshot(): Promise<DesktopSettingsSnapshot> {
    const runtime = await this.backendRuntime()
    const state = this.getStatus()
    const blockers = runtime?.blockers.map(code => BLOCKER_LABELS[code] ?? '本地任务进行中，请等待任务结束') ?? (state.state === 'ready' ? ['无法读取占用状态，请重试'] : [])
    return {
      preferences: this.getPreferences(),
      workspace: { path: this.settings.currentPath, previousPath: this.settings.previousPath, paths: this.paths(), blocked: blockers.length > 0 || this.operation !== 'idle' || state.state === 'starting', blockers, recovery: this.recovery, needsSelection: this.needsSelection },
      service: { state: state.state, apiVersion: state.state === 'ready' ? state.apiVersion : null, baseUrl: state.state === 'ready' ? state.baseUrl : null, message: state.state === 'failed' ? '本地服务启动失败，请重试启动或选择其他工作区' : null },
      runtime: { ...this.options.runtime, backendVersion: runtime?.backendVersion ?? null, pythonVersion: runtime?.pythonVersion ?? null, sqliteVersion: runtime?.sqliteVersion ?? null },
      operation: this.operation,
    }
  }

  async setPreferences(value: unknown): Promise<UiPreferences> {
    this.assertIdle()
    const preferences = validatePreferences(value)
    const previous = this.settings
    const updated = { ...previous, preferences }
    try {
      this.options.applyPreferences(preferences)
      this.options.store.save(updated)
      this.settings = updated
    } catch {
      this.options.applyPreferences(previous.preferences)
      throw new SettingsError('PREFERENCES_SAVE_FAILED', '设置未能保存，已恢复原来的界面偏好')
    }
    return this.getPreferences()
  }

  async chooseWorkspace(source: unknown): Promise<WorkspaceChoice | null> {
    this.assertIdle()
    if (source !== 'choose' && source !== 'previous') throw new SettingsError('INVALID_REQUEST', '无效的工作区选择方式')
    await this.checkIdleTasks()
    let selected: string | null
    if (source === 'previous') {
      if (!this.settings.previousPath) throw new SettingsError('NO_PREVIOUS_WORKSPACE', '没有上一个工作区')
      selected = this.settings.previousPath
    } else selected = await this.options.selectDirectory()
    if (!selected) return null
    this.assertIdle()
    const inspected = inspectWorkspace(selected)
    if (inspected.path === this.settings.currentPath && !this.needsSelection) return null
    ensureWritable(inspected.path)
    this.choice = { ...inspected, id: randomUUID(), expires: Date.now() + 300_000 }
    return { id: this.choice.id, path: this.choice.path, kind: this.choice.kind }
  }

  async confirmWorkspace(id: unknown): Promise<DesktopSettingsSnapshot> {
    const choice = this.choice
    if (typeof id !== 'string' || !choice || choice.id !== id || choice.expires < Date.now()) throw new SettingsError('WORKSPACE_SELECTION_EXPIRED', '目录选择已失效，请重新选择')
    return this.exclusive('switching', async () => {
      this.choice = undefined; this.preview = undefined
      const target = inspectWorkspace(choice.path)
      ensureWritable(target.path)
      const previous = this.settings
      const wasBlocked = this.needsSelection
      await this.quiesce()
      try {
        initializeWorkspace(target.path)
        await this.sidecar?.stop()
        await this.launch(target.path)
        const updated: StoredSettings = { ...previous, currentPath: target.path, previousPath: wasBlocked ? null : previous.currentPath }
        this.options.store.save(updated)
        this.settings = updated; this.needsSelection = false; this.recovery = null
      } catch {
        await this.sidecar?.stop().catch(() => undefined)
        this.settings = previous
        if (!wasBlocked) {
          try {
            await this.launch(previous.currentPath)
            this.record('recovered', 'WORKSPACE_SWITCH_FAILED')
            throw new SettingsError('WORKSPACE_SWITCH_ROLLED_BACK', '未能切换工作区，已恢复原工作区；请选择其他目录后重试')
          } catch (error) {
            if (error instanceof SettingsError && error.code === 'WORKSPACE_SWITCH_ROLLED_BACK') throw error
            this.recovery = '切换失败，原服务恢复也失败。请重试启动或重新选择工作区'
            throw new SettingsError('WORKSPACE_ROLLBACK_FAILED', this.recovery)
          }
        }
        this.needsSelection = true
        throw new SettingsError('WORKSPACE_START_FAILED', '目标工作区无法启动，请重新选择或退出应用')
      }
      return this.snapshot()
    })
  }

  async restart(): Promise<SidecarStatus> {
    return this.exclusive('restarting', async () => {
      if (this.needsSelection) throw new SettingsError('WORKSPACE_SELECTION_REQUIRED', '请先选择可用工作区')
      await this.quiesce()
      await this.sidecar?.stop()
      try { await this.launch(this.settings.currentPath) } catch {
        await this.sidecar?.stop().catch(() => undefined)
        try { await this.launch(this.settings.currentPath); this.record('recovered', 'SERVICE_RESTART_FAILED') } catch {
          throw new SettingsError('SERVICE_RESTART_FAILED', '本地服务重启与恢复均失败，请重试启动或选择其他工作区')
        }
      }
      return this.getStatus()
    })
  }

  async shutdown(): Promise<void> {
    this.quitting = true
    await this.active?.catch(() => undefined)
    await this.sidecar?.stop()
    this.record('stopped')
  }

  async openDirectory(directory: unknown): Promise<{ opened: true }> {
    if (typeof directory !== 'string' || !Object.hasOwn(this.paths(), directory)) throw new SettingsError('INVALID_DIRECTORY', '不支持的目录类型')
    const selected = this.paths()[directory as SettingsDirectory]
    const target = directory === 'database' ? dirname(selected) : selected
    const root = realpathSync(this.settings.currentPath)
    let segment = root
    for (const component of relative(root, target).split(sep).filter(Boolean)) {
      segment = join(segment, component)
      if (existsSync(segment) && lstatSync(segment).isSymbolicLink()) throw new SettingsError('INVALID_DIRECTORY', '不能打开工作区外的符号链接目录')
    }
    mkdirSync(target, { recursive: true })
    const canonical = realpathSync(target)
    if (canonical !== root && !canonical.startsWith(`${root}${sep}`)) throw new SettingsError('INVALID_DIRECTORY', '目录不属于当前工作区')
    const error = await this.options.openPath(canonical)
    if (error) throw new SettingsError('OPEN_DIRECTORY_FAILED', '无法打开目录，请检查访问权限')
    return { opened: true }
  }

  async previewDiagnostics(includeLogs: unknown): Promise<DiagnosticPreview> {
    this.assertIdle()
    if (typeof includeLogs !== 'boolean') throw new SettingsError('INVALID_REQUEST', '日志选择必须为布尔值')
    const snapshot = await this.snapshot()
    const cleanVersion = (value: string | null) => value && /^[\w.+ -]{1,80}$/.test(value) ? value : null
    const content = JSON.stringify({
      schemaVersion: 1,
      createdAt: new Date().toISOString(),
      application: 'AutoFlow',
      runtime: Object.fromEntries(Object.entries(snapshot.runtime).map(([key, value]) => [key, cleanVersion(value)])),
      service: { state: snapshot.service.state, apiVersion: snapshot.service.apiVersion },
      errorCodes: [...new Set(this.events.flatMap(event => event.code ? [event.code] : []))],
      ...(includeLogs ? { logScope: 'current-session-lifecycle-events', logs: this.events.map(event => ({ ...event })) } : {}),
    }, null, 2)
    this.preview = { id: randomUUID(), filename: 'autoflow-diagnostics.json', content, expires: Date.now() + 300_000 }
    return { id: this.preview.id, filename: this.preview.filename, content }
  }

  async saveDiagnostics(id: unknown): Promise<{ saved: boolean; path?: string }> {
    const preview = this.preview
    if (typeof id !== 'string' || !preview || preview.id !== id || preview.expires < Date.now()) throw new SettingsError('DIAGNOSTIC_PREVIEW_EXPIRED', '诊断预览已失效，请重新生成')
    return this.exclusive('exporting', async () => {
      const path = await this.options.selectSavePath(preview.filename)
      if (!path) return { saved: false }
      try { writeAtomic(path, preview.content) } catch { throw new SettingsError('DIAGNOSTIC_SAVE_FAILED', '导出失败：无法写入所选位置，请重新选择') }
      this.record('exported')
      return { saved: true, path }
    })
  }

  async saveAndroidDiagnostic(id: unknown): Promise<{ saved: boolean; path?: string }> {
    this.assertIdle()
    if (typeof id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(id)) throw new SettingsError('INVALID_REQUEST', '诊断标识无效')
    return this.exclusive('exporting', async () => {
      const host = this.getHostStatus()
      if (host.state !== 'ready') throw new SettingsError('SERVICE_UNAVAILABLE', '本地服务尚未就绪，请重试')
      let base: URL
      try { base = new URL(host.baseUrl) } catch { throw new SettingsError('SERVICE_UNAVAILABLE', '本地服务地址无效，请重试') }
      if (base.protocol !== 'http:' || base.hostname !== '127.0.0.1' || !base.port || base.username || base.password || base.search || base.hash || base.pathname !== '/') {
        throw new SettingsError('SERVICE_UNAVAILABLE', '本地服务地址无效，请重试')
      }
      let response: Response
      try {
        response = await (this.options.request ?? fetch)(`${base.origin}/internal/android/management/diagnostics/${encodeURIComponent(id)}`, {
          headers: { accept: 'application/json', 'x-autoflow-host-token': host.hostToken },
          cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(10_000),
        })
      } catch { throw new SettingsError('DIAGNOSTIC_DOWNLOAD_FAILED', '诊断文件暂时不可用，请重新生成') }
      let value: unknown
      try { value = await response.json() } catch { value = null }
      if (!response.ok) {
        const body = value as { error?: { code?: unknown; message?: unknown } } | null
        const code = typeof body?.error?.code === 'string' ? body.error.code : response.status === 410 ? 'ANDROID_DIAGNOSTIC_EXPIRED' : 'DIAGNOSTIC_DOWNLOAD_FAILED'
        const message = typeof body?.error?.message === 'string' ? body.error.message : '诊断文件暂时不可用，请重新生成'
        throw new SettingsError(code, message)
      }
      if (!value || typeof value !== 'object' || !('payload' in value) || !value.payload || typeof value.payload !== 'object' || Array.isArray(value.payload)) throw new SettingsError('DIAGNOSTIC_DOWNLOAD_FAILED', '诊断内容格式无效，请重新生成')
      const envelope = value as { payload: object; createdAt?: unknown; expiresAt?: unknown }
      const expiresAt = typeof envelope.expiresAt === 'string' ? Date.parse(envelope.expiresAt) : NaN
      if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) throw new SettingsError('ANDROID_DIAGNOSTIC_EXPIRED', '诊断下载授权已失效，请重新生成')
      const path = await this.options.selectSavePath('autoflow-android-diagnostic.json')
      if (!path) return { saved: false }
      const current = this.getHostStatus()
      if (current.state !== 'ready' || current.baseUrl !== host.baseUrl || current.hostToken !== host.hostToken || current.dataDir !== host.dataDir) throw new SettingsError('SERVICE_CHANGED', '工作区或本地服务已切换，请重新生成诊断')
      const document = {
        schemaVersion: 1,
        createdAt: typeof envelope.createdAt === 'string' ? envelope.createdAt : new Date().toISOString(),
        application: 'AutoFlow',
        appVersion: this.options.runtime.appVersion,
        payload: envelope.payload,
      }
      try { writeAtomic(path, JSON.stringify(document, null, 2)) } catch { throw new SettingsError('DIAGNOSTIC_SAVE_FAILED', '导出失败：无法写入所选位置，请重新选择') }
      this.record('exported')
      return { saved: true, path }
    })
  }

  private paths(): Record<SettingsDirectory, string> {
    const root = this.settings.currentPath
    return { workspace: root, database: join(root, 'data', 'autoflow.sqlite3'), profiles: join(root, 'workspace', 'profiles'), kernels: join(root, 'data', 'kernels'), logs: join(root, 'logs') }
  }

  private async checkIdleTasks(): Promise<void> {
    const status = this.getStatus()
    if (status.state === 'starting') throw new SettingsError('SERVICE_STARTING', '本地服务正在启动，请稍后再试')
    if (status.state !== 'ready') return
    const runtime = await this.backendRuntime()
    if (!runtime) throw new SettingsError('WORKSPACE_STATUS_UNKNOWN', '无法读取占用状态，请重试')
    if (runtime.blockers.length > 0) throw new SettingsError('WORKSPACE_BUSY', '任务进行中，暂时无法重启或切换工作区；请等待任务结束')
  }

  private async quiesce(): Promise<void> {
    await this.checkIdleTasks()
    const host = this.getHostStatus()
    if (host.state !== 'ready') return
    try {
      const response = await (this.options.request ?? fetch)(`${host.baseUrl}/internal/settings/quiesce`, { method: 'POST', headers: { 'x-autoflow-host-token': host.hostToken }, signal: AbortSignal.timeout(5000) })
      if (response.status === 409) throw new SettingsError('WORKSPACE_BUSY', '任务进行中，暂时无法重启或切换工作区')
      if (!response.ok) throw new Error('quiesce failed')
    } catch (error) {
      // A timed-out response may already have paused the backend.
      await (this.options.request ?? fetch)(`${host.baseUrl}/internal/settings/resume`, { method: 'POST', headers: { 'x-autoflow-host-token': host.hostToken }, signal: AbortSignal.timeout(3000) }).catch(() => undefined)
      if (error instanceof SettingsError) throw error
      throw new SettingsError('WORKSPACE_STATUS_UNKNOWN', '无法确认服务已准备切换，请重试')
    }
  }

  private assertIdle(): void {
    if (this.operation !== 'idle' || this.quitting) throw new SettingsError('OPERATION_IN_PROGRESS', '当前操作尚未完成，请稍候')
  }

  private async exclusive<T>(operation: DesktopSettingsSnapshot['operation'], action: () => Promise<T>): Promise<T> {
    this.assertIdle(); this.operation = operation
    if (operation === 'restarting' || operation === 'switching') this.record(operation)
    const running = Promise.resolve().then(action)
    this.active = running
    try { return await running } catch (error) {
      this.record('failed', error instanceof SettingsError ? error.code : 'LOCAL_OPERATION_FAILED')
      throw error
    } finally { this.operation = 'idle'; if (this.active === running) this.active = undefined }
  }

  private record(event: RuntimeEvent['event'], code: string | null = null): void {
    this.events.push({ timestamp: new Date().toISOString(), event, code }); this.events = this.events.slice(-100)
  }
}
