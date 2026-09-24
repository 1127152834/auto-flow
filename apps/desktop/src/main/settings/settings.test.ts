// @vitest-environment node
import { mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, statSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { SidecarStatus } from '../sidecar/supervisor'
import type { UiPreferences } from '../../shared/settings'
import { SettingsController, type ManagedSidecar, type SettingsControllerOptions } from './controller'
import { DesktopSettingsStore, WORKSPACE_MARKER, inspectWorkspace } from './store'

const roots: string[] = []
const temporary = (name: string) => {
  const path = mkdtempSync(join(tmpdir(), `autoflow-${name}-`))
  roots.push(path)
  return path
}
afterEach(() => {
  vi.restoreAllMocks()
  while (roots.length) rmSync(roots.pop()!, { recursive: true, force: true })
})

const ready = (path: string): SidecarStatus => ({
  state: 'ready', apiVersion: 'v1', instanceId: path, port: 43123,
  baseUrl: 'http://127.0.0.1:43123', token: 'renderer-token',
})

class FakeSidecar implements ManagedSidecar {
  status: SidecarStatus = { state: 'stopped' }
  stops = 0
  constructor(readonly path: string, private readonly failure?: Error) {}
  async start(): Promise<SidecarStatus> {
    if (this.failure) throw this.failure
    return this.status = ready(this.path)
  }
  async stop(): Promise<void> { this.stops += 1; this.status = { state: 'stopped' } }
  getStatus(): SidecarStatus { return this.status }
  getHostStatus() {
    return this.status.state === 'ready'
      ? { state: 'ready' as const, baseUrl: this.status.baseUrl, hostToken: 'host-token', dataDir: this.path }
      : { state: 'stopped' as const }
  }
}

function response(value: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } }))
}

function harness(options: Partial<SettingsControllerOptions> & { userData?: string } = {}) {
  const userData = options.userData ?? temporary('settings')
  const store = options.store ?? new DesktopSettingsStore(userData)
  const sidecars: FakeSidecar[] = []
  const failures: Array<Error | undefined> = []
  const request = vi.fn((input: string | URL | Request) => {
    const url = String(input)
    if (url.endsWith('/api/v1/settings/runtime')) return response({ apiVersion: 'v1', backendVersion: '0.1.0', pythonVersion: '3.11.0', sqliteVersion: '3.0.0', blockers: [] })
    return response({ paused: url.endsWith('/quiesce') })
  }) as unknown as typeof fetch
  const controller = new SettingsController({
    store,
    createSidecar: path => {
      const sidecar = new FakeSidecar(path, failures.shift())
      sidecars.push(sidecar)
      return sidecar
    },
    runtime: { appVersion: '0.1.0', electronVersion: '41.0.0', chromeVersion: '140.0.0', nodeVersion: '24.0.0', platform: 'macos', arch: 'arm64' },
    selectDirectory: async () => null,
    selectSavePath: async () => null,
    openPath: async () => '',
    applyPreferences: () => undefined,
    request,
    ...options,
  })
  return { controller, store, sidecars, failures, request, userData }
}

async function expectCode(action: Promise<unknown>, code: string) {
  await expect(action).rejects.toMatchObject({ code })
}

describe('desktop settings storage', () => {
  it('rejects a marked workspace whose database is a dangling symlink', () => {
    const root = temporary('linked-database')
    new DesktopSettingsStore(root).load()
    mkdirSync(join(root, 'data'))
    symlinkSync(join(root, 'missing.sqlite3'), join(root, 'data', 'autoflow.sqlite3'))
    expect(() => inspectWorkspace(root)).toThrowError(expect.objectContaining({ code: 'INVALID_WORKSPACE' }))
  })

  it('persists preferences and restores a corrupt primary from backup', () => {
    const root = temporary('backup')
    const store = new DesktopSettingsStore(root)
    const initial = store.load().settings
    store.save({ ...initial, preferences: { zoom: 110, motion: 'reduce' } })
    writeFileSync(store.path, '{broken')
    const recovered = new DesktopSettingsStore(root).load()
    expect(recovered.recovery).toContain('备份恢复')
    expect(recovered.settings.preferences).toEqual({ zoom: 100, motion: 'system' })
    expect(readFileSync(store.path, 'utf8')).toContain('"zoom": 100')
  })

  it('requires selection when primary and backup are both corrupt', () => {
    const root = temporary('double-bad')
    const store = new DesktopSettingsStore(root)
    store.load()
    store.save({ ...store.load().settings, preferences: { zoom: 125, motion: 'full' } })
    writeFileSync(store.path, '{bad')
    writeFileSync(`${store.path}.bak`, '{bad')
    expect(new DesktopSettingsStore(root).load()).toMatchObject({ needsSelection: true })
  })

  it('initializes only empty directories and rejects unmarked or legacy data', () => {
    const empty = temporary('empty')
    expect(inspectWorkspace(empty)).toMatchObject({ kind: 'empty', path: realpathSync(empty) })
    const unmarked = temporary('unmarked')
    writeFileSync(join(unmarked, 'data.txt'), 'occupied')
    expect(() => inspectWorkspace(unmarked)).toThrowError(expect.objectContaining({ code: 'UNRECOGNIZED_WORKSPACE' }))
    const legacy = temporary('legacy')
    writeFileSync(join(legacy, '.autoflow-rebuild-workspace'), 'legacy')
    expect(() => inspectWorkspace(legacy)).toThrowError(expect.objectContaining({ code: 'UNRECOGNIZED_WORKSPACE' }))
  })
})

describe('workspace and preference controller', () => {
  it('blocks workspace selection and restart while browser resources are in use', async () => {
    let occupied = true
    const target = temporary('profile-in-use')
    const selectDirectory = vi.fn(async () => target)
    const h = harness({ selectDirectory, request: vi.fn(async () => new Response(JSON.stringify({ blockers: occupied ? ['profile_in_use', 'test_browser_process_active'] : [] }))) })
    await h.controller.start()
    expect((await h.controller.snapshot()).workspace.blocked).toBe(true)
    await expectCode(h.controller.chooseWorkspace('choose'), 'WORKSPACE_BUSY')
    await expectCode(h.controller.restart(), 'WORKSPACE_BUSY')
    expect(selectDirectory).not.toHaveBeenCalled()
    expect(h.sidecars[0].stops).toBe(0)
    occupied = false
    const choice = await h.controller.chooseWorkspace('choose')
    await h.controller.confirmWorkspace(choice!.id)
    expect(h.sidecars[0].stops).toBe(1)
  })

  it('labels every project-lifecycle blocker with actionable text instead of the generic fallback', async () => {
    const h = harness({ request: vi.fn(async () => new Response(JSON.stringify({ blockers: [
      'project_batches_active', 'project_lifecycle_pending', 'project_excel_operation_active',
      'project_data_status_batch_active', 'project_manual_item_pending', 'project_sync_outcome_unknown',
      'workflow_runs_active', 'workflow_worker_busy', 'workflow_process_active',
      'android_management_active', 'android_console_active',
    ] }))) })
    await h.controller.start()
    const { blockers } = (await h.controller.snapshot()).workspace
    expect(blockers).not.toContain('本地任务进行中，请等待任务结束')
    expect(new Set(blockers).size).toBe(blockers.length)
    expect(blockers).toContain('项目批次正在运行')
    expect(blockers).toContain('项目归档或删除正在收尾')
  })

  it('reads a synchronous runtime snapshot without mixing workspace identity and credentials during a switch', async () => {
    const target = temporary('runtime-context')
    const h = harness({ selectDirectory: async () => target })
    await h.controller.start()
    const old = h.controller.getRuntimeContext()
    expect(old).toMatchObject({ workspaceKey: realpathSync(h.userData), sidecar: { state: 'ready', token: 'renderer-token' }, operation: 'idle' })
    expect(JSON.stringify(old)).not.toContain('host-token')
    const choice = await h.controller.chooseWorkspace('choose')
    const switching = h.controller.confirmWorkspace(choice!.id)
    expect(h.controller.getRuntimeContext()).toMatchObject({ workspaceKey: old.workspaceKey, sidecar: { state: 'starting' }, operation: 'switching' })
    await switching
    expect(h.controller.getRuntimeContext()).toMatchObject({ workspaceKey: realpathSync(target), sidecar: { state: 'ready', instanceId: realpathSync(target) }, operation: 'idle' })
  })

  it('rolls back applied preferences when persistence fails', async () => {
    const applied: UiPreferences[] = []
    const h = harness({ applyPreferences: value => applied.push(value) })
    vi.spyOn(h.store, 'save').mockImplementation(() => { throw new Error('disk full') })
    await expectCode(h.controller.setPreferences({ zoom: 110, motion: 'reduce' }), 'PREFERENCES_SAVE_FAILED')
    expect(applied).toEqual([{ zoom: 110, motion: 'reduce' }, { zoom: 100, motion: 'system' }])
    expect(h.controller.getPreferences()).toEqual({ zoom: 100, motion: 'system' })
  })

  it('handles chooser cancellation and current-path selection as no-ops', async () => {
    const h = harness()
    await h.controller.start()
    expect(await h.controller.chooseWorkspace('choose')).toBeNull()
    const sameRoot = temporary('same')
    const same = harness({ userData: sameRoot, selectDirectory: async () => sameRoot })
    await same.controller.start()
    const stopCount = same.sidecars[0].stops
    expect(await same.controller.chooseWorkspace('choose')).toBeNull()
    expect(same.sidecars[0].stops).toBe(stopCount)
  })

  it('rejects invalid and expired choice ids', async () => {
    const target = temporary('choice')
    const h = harness({ selectDirectory: async () => target })
    await h.controller.start()
    const choice = await h.controller.chooseWorkspace('choose')
    await expectCode(h.controller.confirmWorkspace('wrong'), 'WORKSPACE_SELECTION_EXPIRED')
    vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 300_001)
    await expectCode(h.controller.confirmWorkspace(choice!.id), 'WORKSPACE_SELECTION_EXPIRED')
  })

  it('stops before switching and saves only after the target is ready', async () => {
    const target = temporary('switch')
    const h = harness({ selectDirectory: async () => target })
    await h.controller.start()
    const oldPath = h.userData
    const choice = await h.controller.chooseWorkspace('choose')
    const snapshot = await h.controller.confirmWorkspace(choice!.id)
    expect(h.sidecars[0].stops).toBe(1)
    expect(snapshot.workspace).toMatchObject({ path: realpathSync(target), previousPath: realpathSync(oldPath) })
    expect(JSON.parse(readFileSync(h.store.path, 'utf8')).currentPath).toBe(realpathSync(target))
    expect(JSON.parse(readFileSync(join(target, WORKSPACE_MARKER), 'utf8'))).toMatchObject({ schemaVersion: 1 })
  })

  it('reports target failure after restoring the original service', async () => {
    const target = temporary('rollback')
    const h = harness({ selectDirectory: async () => target })
    await h.controller.start()
    h.failures.push(new Error('target failed'), undefined)
    const choice = await h.controller.chooseWorkspace('choose')
    await expectCode(h.controller.confirmWorkspace(choice!.id), 'WORKSPACE_SWITCH_ROLLED_BACK')
    expect(h.controller.getStatus().state).toBe('ready')
    expect(h.store.load().settings.currentPath).toBe(realpathSync(h.userData))
  })

  it('distinguishes failure of both target and rollback', async () => {
    const target = temporary('double-failure')
    const h = harness({ selectDirectory: async () => target })
    await h.controller.start()
    h.failures.push(new Error('target failed'), new Error('rollback failed'))
    const choice = await h.controller.chooseWorkspace('choose')
    await expectCode(h.controller.confirmWorkspace(choice!.id), 'WORKSPACE_ROLLBACK_FAILED')
    expect((await h.controller.snapshot()).workspace.recovery).toContain('恢复也失败')
  })

  it('does not stop the service when quiesce is blocked', async () => {
    const target = temporary('blocked')
    const request = vi.fn((input: string | URL | Request) => String(input).endsWith('/api/v1/settings/runtime')
      ? response({ apiVersion: 'v1', backendVersion: '0.1.0', pythonVersion: '3.11', sqliteVersion: '3', blockers: [] })
      : response({ error: { details: { blockers: ['kernel_operation_active'] } } }, 409)) as unknown as typeof fetch
    const h = harness({ selectDirectory: async () => target, request })
    await h.controller.start()
    const choice = await h.controller.chooseWorkspace('choose')
    await expectCode(h.controller.confirmWorkspace(choice!.id), 'WORKSPACE_BUSY')
    expect(h.sidecars[0].stops).toBe(0)
  })
})

describe('diagnostic preview and local save', () => {
  it('defaults to no logs and omits tokens and workspace paths', async () => {
    const h = harness()
    await h.controller.start()
    const preview = await h.controller.previewDiagnostics(false)
    expect(preview.content).not.toContain('logs')
    expect(preview.content).not.toContain('renderer-token')
    expect(preview.content).not.toContain('host-token')
    expect(preview.content).not.toContain(h.userData)
  })

  it('writes exactly the reviewed preview and treats save cancellation as unsaved', async () => {
    const outputRoot = temporary('diagnostic')
    const output = join(outputRoot, 'diagnostic.json')
    let selected: string | null = null
    const h = harness({ selectSavePath: async () => selected })
    await h.controller.start()
    const preview = await h.controller.previewDiagnostics(true)
    expect(await h.controller.saveDiagnostics(preview.id)).toEqual({ saved: false })
    selected = output
    expect(await h.controller.saveDiagnostics(preview.id)).toEqual({ saved: true, path: output })
    expect(readFileSync(output, 'utf8')).toBe(preview.content)
  })

  it('rejects expired previews and reports unwritable destinations', async () => {
    const directory = temporary('unwritable-target')
    const h = harness({ selectSavePath: async () => directory })
    await h.controller.start()
    const preview = await h.controller.previewDiagnostics(false)
    await expectCode(h.controller.saveDiagnostics(preview.id), 'DIAGNOSTIC_SAVE_FAILED')
    const next = await h.controller.previewDiagnostics(false)
    vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 300_001)
    await expectCode(h.controller.saveDiagnostics(next.id), 'DIAGNOSTIC_PREVIEW_EXPIRED')
  })

  it('downloads an Android diagnostic by id in the main process and writes it mode 0600', async () => {
    const output = join(temporary('android-diagnostic'), 'android.json')
    const h = harness({
      selectSavePath: async () => output,
      request: vi.fn((input: string | URL | Request) => String(input).includes('/internal/android/management/diagnostics/')
        ? response({ id: 'diag-1', requestId: 'diag-1', state: 'ready', payload: { environment: { status: 'unknown' } }, createdAt: '2026-09-22T00:00:00Z', expiresAt: '2099-01-01T00:00:00Z' })
        : response({ apiVersion: 'v1', backendVersion: '0.1.0', pythonVersion: '3.11.0', sqliteVersion: '3.0.0', blockers: [] })) as unknown as typeof fetch,
    })
    await h.controller.start()

    await expect(h.controller.saveAndroidDiagnostic('diag-1')).resolves.toEqual({ saved: true, path: output })
    expect(JSON.parse(readFileSync(output, 'utf8'))).toMatchObject({ application: 'AutoFlow', payload: { environment: { status: 'unknown' } } })
    expect(statSync(output).mode & 0o777).toBe(0o600)
  })

  it('rejects a missing or expired Android diagnostic before opening a save dialog', async () => {
    const selectSavePath = vi.fn(async () => join(temporary('android-diagnostic-expired'), 'android.json'))
    const h = harness({
      selectSavePath,
      request: vi.fn((input: string | URL | Request) => String(input).includes('/internal/android/management/diagnostics/')
        ? response({ error: { code: 'ANDROID_DIAGNOSTIC_EXPIRED', message: 'expired' } }, 410)
        : response({ apiVersion: 'v1', backendVersion: '0.1.0', pythonVersion: '3.11.0', sqliteVersion: '3.0.0', blockers: [] })) as unknown as typeof fetch,
    })
    await h.controller.start()

    await expectCode(h.controller.saveAndroidDiagnostic('diag-expired'), 'ANDROID_DIAGNOSTIC_EXPIRED')
    expect(selectSavePath).not.toHaveBeenCalled()
  })
})
