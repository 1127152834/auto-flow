// @vitest-environment node
import { randomUUID } from 'node:crypto'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, it } from 'vitest'
import { SidecarSupervisor } from '../sidecar/supervisor'
import { SettingsController } from './controller'
import { DesktopSettingsStore } from './store'

const backendDirectory = resolve(dirname(fileURLToPath(import.meta.url)), '../../../../backend')

it('runs settings and workspace lifecycle against real local sidecars', async () => {
  const root = mkdtempSync(join(tmpdir(), 'autoflow-settings-integration-'))
  const userData = join(root, 'workspace-a')
  const workspaceB = join(root, 'workspace-b')
  const diagnosticPath = join(root, 'diagnostic.json')
  mkdirSync(userData)
  mkdirSync(workspaceB)

  const supervisors: SidecarSupervisor[] = []
  let selectedDirectory: string | null = workspaceB
  const selectedSavePath: string | null = diagnosticPath
  let holdBRuntime = false
  let signalBRuntime!: () => void
  let releaseBRuntime!: () => void
  const bRuntimeStarted = new Promise<void>(resolveStarted => { signalBRuntime = resolveStarted })
  const bRuntimeRelease = new Promise<void>(resolveRelease => { releaseBRuntime = resolveRelease })
  const store = new DesktopSettingsStore(userData)
  let controller: SettingsController | undefined

  try {
    controller = new SettingsController({
      store,
      createSidecar: dataDir => {
        const supervisor = new SidecarSupervisor({
          instanceId: randomUUID(),
          dataDir,
          backendDirectory,
          production: false,
          timeoutMs: 20_000,
        })
        supervisors.push(supervisor)
        return supervisor
      },
      runtime: {
        appVersion: '0.1.0', electronVersion: process.versions.electron ?? 'test',
        chromeVersion: process.versions.chrome ?? 'test', nodeVersion: process.versions.node,
        platform: process.platform === 'darwin' ? 'macos' : process.platform === 'win32' ? 'windows' : 'linux',
        arch: process.arch,
      },
      selectDirectory: async () => selectedDirectory,
      selectSavePath: async () => selectedSavePath,
      openPath: async () => '',
      applyPreferences: () => undefined,
      request: (async (input, init) => {
        const url = String(input)
        const bStatus = supervisors[1]?.getStatus()
        if (holdBRuntime && bStatus?.state === 'ready' && url === `${bStatus.baseUrl}/api/v1/settings/runtime`) {
          holdBRuntime = false
          signalBRuntime()
          await bRuntimeRelease
        }
        return fetch(input, init)
      }) as typeof fetch,
    })

    await controller.start()
    const aStatus = controller.getStatus()
    const aHost = controller.getHostStatus()
    expect(aStatus.state).toBe('ready')
    expect(aHost.state).toBe('ready')
    if (aStatus.state !== 'ready' || aHost.state !== 'ready') throw new Error('workspace A did not start')

    const authA = { 'x-autoflow-token': aStatus.token }
    const runtimeA = await fetch(`${aStatus.baseUrl}/api/v1/settings/runtime`, { headers: authA })
    const dashboardA = await fetch(`${aStatus.baseUrl}/api/v1/dashboard`, { headers: authA })
    expect(runtimeA.status).toBe(200)
    expect(await runtimeA.json()).toMatchObject({ apiVersion: 'v1', blockers: [] })
    expect(dashboardA.status).toBe(200)
    expect(await dashboardA.json()).toMatchObject({ profiles: 0, enabledProxies: 0, proxyGroups: 0, installedKernels: 0 })

    await controller.setPreferences({ zoom: 110, motion: 'reduce' })
    const sentinel = join(userData, 'workspace', 'a-sentinel.txt')
    writeFileSync(sentinel, 'workspace-a')

    const choiceB = await controller.chooseWorkspace('choose')
    expect(choiceB).toMatchObject({ kind: 'empty' })
    holdBRuntime = true
    const switchingToB = controller.confirmWorkspace(choiceB!.id)
    await bRuntimeStarted
    expect(controller.getStatus().state).toBe('ready')
    expect(controller.getPublicStatus()).toEqual({ state: 'starting' })
    releaseBRuntime()
    const snapshotB = await switchingToB
    expect(snapshotB.service.state).toBe('ready')
    expect(snapshotB.preferences).toEqual({ zoom: 110, motion: 'reduce' })
    await expect(fetch(`${aStatus.baseUrl}/health`, { signal: AbortSignal.timeout(1_000) })).rejects.toThrow()
    expect(existsSync(join(workspaceB, 'data', 'autoflow.sqlite3'))).toBe(true)
    expect(existsSync(join(workspaceB, 'workspace', 'a-sentinel.txt'))).toBe(false)
    expect(readFileSync(sentinel, 'utf8')).toBe('workspace-a')
    const persistedB = JSON.parse(readFileSync(store.path, 'utf8'))
    expect(persistedB).toMatchObject({ currentPath: realpathSync(workspaceB), preferences: { zoom: 110, motion: 'reduce' } })
    expect(dirname(store.path)).toBe(userData)

    selectedDirectory = null
    const choiceA = await controller.chooseWorkspace('previous')
    await controller.confirmWorkspace(choiceA!.id)
    expect(controller.getStatus().state).toBe('ready')
    expect(readFileSync(sentinel, 'utf8')).toBe('workspace-a')
    expect(controller.getPreferences()).toEqual({ zoom: 110, motion: 'reduce' })

    const current = controller.getStatus()
    const currentHost = controller.getHostStatus()
    if (current.state !== 'ready' || currentHost.state !== 'ready') throw new Error('workspace A did not resume')
    const preview = await controller.previewDiagnostics(false)
    expect(preview.content).not.toContain(current.token)
    expect(preview.content).not.toContain(currentHost.hostToken)
    expect(preview.content).not.toContain(userData)
    expect(preview.content).not.toContain(workspaceB)
    expect(await controller.saveDiagnostics(preview.id)).toEqual({ saved: true, path: diagnosticPath })
    expect(readFileSync(diagnosticPath, 'utf8')).toBe(preview.content)

    const finalBaseUrl = current.baseUrl
    await controller.shutdown()
    await expect(fetch(`${finalBaseUrl}/health`, { signal: AbortSignal.timeout(1_000) })).rejects.toThrow()
  } finally {
    await controller?.shutdown().catch(() => undefined)
    await Promise.allSettled(supervisors.map(supervisor => supervisor.stop()))
    rmSync(root, { recursive: true, force: true })
  }
}, 60_000)
