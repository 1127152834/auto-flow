import { randomBytes } from 'node:crypto'
import { spawn, type ChildProcess } from 'node:child_process'
import { platform } from 'node:process'
import { resolveBackendEnvironment } from '../platform/paths'
import { parseReadyLine, type SidecarReady } from './ready-protocol'

export type SidecarStatus =
  | { state: 'starting' | 'stopped' }
  | { state: 'failed'; message: string }
  | { state: 'ready'; apiVersion: 'v1'; instanceId: string; port: number; baseUrl: string; token: string }

export type SidecarEvent =
  | { type: 'spawned' }
  | ({ type: 'ready' } & SidecarReady & { baseUrl: string; token: string })
  | { type: 'failed'; message: string }
  | { type: 'stopped' }

export function initialSidecarStatus(): SidecarStatus { return { state: 'stopped' } }

export function applySidecarEvent(_status: SidecarStatus, event: SidecarEvent): SidecarStatus {
  if (event.type === 'spawned') return { state: 'starting' }
  if (event.type === 'ready') return { state: 'ready', apiVersion: 'v1', instanceId: event.instanceId, port: event.port, baseUrl: event.baseUrl, token: event.token }
  if (event.type === 'failed') return { state: 'failed', message: event.message }
  return { state: 'stopped' }
}

export type SupervisorOptions = {
  instanceId: string
  dataDir?: string
  backendDirectory?: string
  rendererOrigin?: string
  production?: boolean
  sidecarPath?: string
  timeoutMs?: number
  onStatus?: (status: SidecarStatus) => void
}

export async function validateSidecarHealth(
  baseUrl: string,
  token: string,
  ready: SidecarReady,
): Promise<void> {
  const response = await fetch(`${baseUrl}/health`, { headers: { 'x-autoflow-token': token } })
  if (!response.ok) throw new Error(`sidecar health check failed with status ${response.status}`)
  const body: unknown = await response.json()
  if (!body || typeof body !== 'object') throw new Error('invalid sidecar health response')
  const data = body as Record<string, unknown>
  if (data.status !== 'ok' || data.apiVersion !== ready.apiVersion || data.instanceId !== ready.instanceId) {
    throw new Error('sidecar health metadata mismatch')
  }
}

export class SidecarSupervisor {
  private child: ChildProcess | undefined
  private status: SidecarStatus = initialSidecarStatus()
  private stopping = false
  private startupGeneration = 0
  private hostToken: string | undefined
  private pendingStart: { generation: number; timer: ReturnType<typeof setTimeout>; reject: (reason?: unknown) => void } | undefined

  constructor(private readonly options: SupervisorOptions) {}

  getStatus(): SidecarStatus { return this.status }

  // Only main-process IPC uses this. Never include it in renderer status events.
  getHostStatus(): { state: 'ready'; baseUrl: string; hostToken: string } | { state: 'stopped' } {
    if (this.status.state !== 'ready' || !this.hostToken) return { state: 'stopped' }
    return { state: 'ready', baseUrl: this.status.baseUrl, hostToken: this.hostToken }
  }

  async start(): Promise<SidecarStatus> {
    if (this.child) return this.status
    if (this.options.production && !this.options.sidecarPath) throw new Error('production sidecarPath is required')
    if (!this.options.dataDir) throw new Error('sidecar dataDir is required')
    const token = randomBytes(32).toString('hex')
    this.hostToken = randomBytes(32).toString('hex')
    const sidecarArgs = [
      '--port', '0',
      '--instance-id', this.options.instanceId,
      '--parent-pid', String(process.pid),
      '--data-dir', this.options.dataDir,
    ]
    if (!this.options.production && !this.options.backendDirectory) throw new Error('backendDirectory is required in development')
    const args = this.options.production ? sidecarArgs : ['run', '--directory', this.options.backendDirectory!, 'python', '-m', 'autoflow', ...sidecarArgs]
    const command = this.options.production ? this.options.sidecarPath! : 'uv'
    const generation = ++this.startupGeneration
    this.update(applySidecarEvent(this.status, { type: 'spawned' }))
    const child = spawn(command, args, {
      env: { ...process.env, AUTOFLOW_INSTANCE_TOKEN: token, AUTOFLOW_HOST_TOKEN: this.hostToken, ...resolveBackendEnvironment(this.options.dataDir), AUTOFLOW_RENDERER_ORIGIN: this.options.rendererOrigin ?? 'null' },
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    })
    this.child = child
    child.stderr?.resume()
    let buffer = ''
    const ready = new Promise<SidecarStatus>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingStart = undefined
        reject(new Error('sidecar readiness timeout'))
        void this.stop()
      }, this.options.timeoutMs ?? 15000)
      this.pendingStart = { generation, timer, reject }
      child.stdout?.on('data', (chunk: Buffer | string) => {
        buffer += chunk.toString()
        const lines = buffer.split(/\r?\n/)
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('AUTOFLOW_READY ')) continue
          void (async () => {
            try {
              const parsed = parseReadyLine(line)
              const baseUrl = `http://127.0.0.1:${parsed.port}`
              await validateSidecarHealth(baseUrl, token, parsed)
              if (this.startupGeneration !== generation || this.child !== child || this.stopping) {
                throw new Error('sidecar start cancelled')
              }
              const next = applySidecarEvent(this.status, { type: 'ready', ...parsed, baseUrl, token })
              clearTimeout(timer); this.pendingStart = undefined; this.update(next); resolve(next)
            } catch (error) {
              clearTimeout(timer)
              const current = this.startupGeneration === generation && this.child === child
              if (current) {
                this.pendingStart = undefined
                void this.stop()
              }
              reject(error)
            }
          })()
        }
      })
      child.once('error', error => { clearTimeout(timer); this.pendingStart = undefined; reject(error) })
      child.once('exit', code => {
        this.hostToken = undefined
        this.child = undefined
        if (this.stopping) return
        clearTimeout(timer)
        this.pendingStart = undefined
        const message = `sidecar exited with code ${code ?? 'unknown'}`
        if (this.status.state === 'ready') this.update(applySidecarEvent(this.status, { type: 'failed', message }))
        else reject(new Error(message))
      })
    })
    try {
      return await ready
    } catch (error) {
      if (!(error instanceof Error && error.message === 'sidecar stopped')) {
        this.update(applySidecarEvent(this.status, { type: 'failed', message: error instanceof Error ? error.message : String(error) }))
      }
      throw error
    }
  }

  async restart(): Promise<SidecarStatus> { await this.stop(); return this.start() }

  async stop(): Promise<void> {
    this.hostToken = undefined
    const child = this.child
    if (!child || this.stopping) return
    this.startupGeneration += 1
    if (this.pendingStart) {
      clearTimeout(this.pendingStart.timer)
      const pending = this.pendingStart
      this.pendingStart = undefined
      pending.reject(new Error('sidecar stopped'))
    }
    this.stopping = true
    child.kill('SIGTERM')
    await new Promise<void>(resolve => {
      const timer = setTimeout(() => {
        if (platform === 'win32' && child.pid) spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'])
        else child.kill('SIGKILL')
        resolve()
      }, 3000)
      child.once('exit', () => { clearTimeout(timer); resolve() })
    })
    this.child = undefined; this.stopping = false
    this.update(applySidecarEvent(this.status, { type: 'stopped' }))
  }

  private update(status: SidecarStatus): void { this.status = status; this.options.onStatus?.(status) }
}
