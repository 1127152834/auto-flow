import { randomUUID } from 'node:crypto'
import type { SidecarStatus } from '../shared/runtime'

type ShortcutRegistry = {
  register(accelerator: string, callback: () => void): boolean
  unregister(accelerator: string): void
}

type Registration = { task_id: string; hotkey: string }

export function toElectronAccelerator(value: string): string | null {
  const aliases: Record<string, string> = {
    ctrl: 'Control', cmd: 'Command', alt: 'Alt', shift: 'Shift', esc: 'Escape',
    enter: 'Return', pageup: 'PageUp', pagedown: 'PageDown', space: 'Space',
    up: 'Up', down: 'Down', left: 'Left', right: 'Right', grave: '`', minus: '-',
    equal: '=', bracketleft: '[', bracketright: ']', backslash: '\\',
    semicolon: ';', quote: "'", comma: ',', period: '.', slash: '/',
  }
  const parts = value.split('+').map(part => part.trim().toLowerCase()).filter(Boolean)
  if (!parts.length) return null
  const mapped = parts.map(part => aliases[part] ?? (/^f(?:[1-9]|1[0-2])$/.test(part) ? part.toUpperCase() : part.length === 1 ? part.toUpperCase() : part[0]!.toUpperCase() + part.slice(1)))
  return mapped.some(part => !['Control', 'Command', 'Alt', 'Shift'].includes(part)) ? mapped.join('+') : null
}

export class ScheduledHotkeyController {
  private timer: ReturnType<typeof setInterval> | undefined
  private reconciling = false
  private registered = new Map<string, { accelerator: string; instanceId: string }>()

  constructor(private readonly dependencies: {
    shortcuts: ShortcutRegistry
    getSidecarStatus(): SidecarStatus
    request?: typeof fetch
    intervalMs?: number
  }) {}

  start(): void {
    if (this.timer) return
    void this.reconcile()
    this.timer = setInterval(() => void this.reconcile(), this.dependencies.intervalMs ?? 1000)
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer)
    this.timer = undefined
    for (const value of this.registered.values()) this.dependencies.shortcuts.unregister(value.accelerator)
    this.registered.clear()
  }

  async reconcile(): Promise<void> {
    if (this.reconciling) return
    const sidecar = this.dependencies.getSidecarStatus()
    if (sidecar.state !== 'ready') {
      this.stopRegistrations()
      return
    }
    this.reconciling = true
    try {
      const response = await (this.dependencies.request ?? fetch)(`${sidecar.baseUrl}/api/scheduled-tasks/hotkeys/registrations`, {
        headers: { 'x-autoflow-token': sidecar.token },
        signal: AbortSignal.timeout(3000),
      })
      if (!response.ok) return
      const body: unknown = await response.json()
      if (!Array.isArray(body)) return
      const desired = new Map<string, string>()
      for (const item of body as Registration[]) {
        if (!item || typeof item.task_id !== 'string' || typeof item.hotkey !== 'string') continue
        const accelerator = toElectronAccelerator(item.hotkey)
        if (accelerator) desired.set(item.task_id, accelerator)
      }
      for (const [taskId, current] of this.registered) {
        if (desired.get(taskId) !== current.accelerator || current.instanceId !== sidecar.instanceId) {
          this.dependencies.shortcuts.unregister(current.accelerator)
          this.registered.delete(taskId)
        }
      }
      for (const [taskId, accelerator] of desired) {
        if (this.registered.has(taskId)) continue
        const instanceId = sidecar.instanceId
        if (this.dependencies.shortcuts.register(accelerator, () => void this.trigger(taskId, instanceId))) {
          this.registered.set(taskId, { accelerator, instanceId })
        }
      }
    } catch {
      // Keep registrations during a transient service failure; each callback is instance-fenced.
    } finally {
      this.reconciling = false
    }
  }

  private stopRegistrations(): void {
    for (const value of this.registered.values()) this.dependencies.shortcuts.unregister(value.accelerator)
    this.registered.clear()
  }

  private async trigger(taskId: string, instanceId: string): Promise<void> {
    const sidecar = this.dependencies.getSidecarStatus()
    if (sidecar.state !== 'ready' || sidecar.instanceId !== instanceId) return
    const commandId = randomUUID()
    const request = this.dependencies.request ?? fetch
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const response = await request(`${sidecar.baseUrl}/api/scheduled-tasks/hotkeys/${encodeURIComponent(taskId)}/trigger`, {
          method: 'POST',
          headers: {
            'x-autoflow-token': sidecar.token,
            'Idempotency-Key': commandId,
          },
          signal: AbortSignal.timeout(3000),
        })
        if (response.ok || response.status < 500) return
      } catch {
        // Retry once with the same command id; the backend deduplicates accepted triggers.
      }
    }
  }
}
