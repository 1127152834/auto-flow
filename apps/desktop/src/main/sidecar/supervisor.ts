import { randomBytes } from 'node:crypto'
import { spawn, type ChildProcess } from 'node:child_process'
import { platform } from 'node:process'
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
  production?: boolean
  sidecarPath?: string
  timeoutMs?: number
  onStatus?: (status: SidecarStatus) => void
}

export class SidecarSupervisor {
  private child: ChildProcess | undefined
  private status: SidecarStatus = initialSidecarStatus()
  private stopping = false

  constructor(private readonly options: SupervisorOptions) {}

  getStatus(): SidecarStatus { return this.status }

  async start(): Promise<SidecarStatus> {
    if (this.child) return this.status
    const token = randomBytes(32).toString('hex')
    const sidecarArgs = ['--port', '0', '--instance-id', this.options.instanceId, '--parent-pid', String(process.pid)]
    const args = this.options.production ? sidecarArgs : ['-m', 'autoflow', ...sidecarArgs]
    const command = this.options.production ? (this.options.sidecarPath ?? 'autoflow-sidecar') : 'python'
    this.update(applySidecarEvent(this.status, { type: 'spawned' }))
    const child = spawn(command, args, {
      env: { ...process.env, AUTOFLOW_INSTANCE_TOKEN: token, ...(this.options.dataDir ? { AUTOFLOW_DATA_DIR: this.options.dataDir } : {}) },
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    })
    this.child = child
    let buffer = ''
    const ready = new Promise<SidecarStatus>((resolve, reject) => {
      const timer = setTimeout(() => { reject(new Error('sidecar readiness timeout')); void this.stop() }, this.options.timeoutMs ?? 15000)
      child.stdout?.on('data', (chunk: Buffer | string) => {
        buffer += chunk.toString()
        const lines = buffer.split(/\r?\n/)
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('AUTOFLOW_READY ')) continue
          try {
            const parsed = parseReadyLine(line)
            const next = applySidecarEvent(this.status, { type: 'ready', ...parsed, baseUrl: `http://127.0.0.1:${parsed.port}`, token })
            clearTimeout(timer); this.update(next); resolve(next)
          } catch (error) { clearTimeout(timer); void this.stop(); reject(error) }
        }
      })
      child.once('error', error => { clearTimeout(timer); reject(error) })
      child.once('exit', code => {
        this.child = undefined
        if (this.stopping) return
        const message = `sidecar exited with code ${code ?? 'unknown'}`
        if (this.status.state === 'ready') this.update(applySidecarEvent(this.status, { type: 'failed', message }))
        else { clearTimeout(timer); reject(new Error(message)) }
      })
    })
    try { return await ready } catch (error) { this.update(applySidecarEvent(this.status, { type: 'failed', message: error instanceof Error ? error.message : String(error) })); throw error }
  }

  async restart(): Promise<SidecarStatus> { await this.stop(); return this.start() }

  async stop(): Promise<void> {
    const child = this.child
    if (!child || this.stopping) return
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
