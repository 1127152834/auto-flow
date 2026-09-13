import { parseServerSentEvents } from '../../../shared/api/events'
import { studioFetch } from './transport'

// The source handlers retain their payload types. Only this compatibility boundary is erased.
type Listener = (...args: never[]) => void
export class StudioEventClient {
  connected = false
  private listeners = new Map<string, Set<Listener>>()
  private controller = new AbortController()
  private sequence = 0
  private retry: ReturnType<typeof setTimeout> | undefined
  constructor(private baseUrl: string) { queueMicrotask(() => void this.listen()) }
  on(event: string, listener: Listener) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set())
    this.listeners.get(event)!.add(listener)
    return this
  }
  off(event: string, listener?: Listener) {
    if (listener) this.listeners.get(event)?.delete(listener)
    else this.listeners.delete(event)
    return this
  }
  removeAllListeners() { this.listeners.clear() }
  emit(event: string, data: unknown, commandId = crypto.randomUUID()) {
    void this.sendCommand(commandId, event, data)
    return commandId
  }
  async queryCommand(commandId: string): Promise<Record<string, unknown>> {
    const response = await studioFetch(`${this.baseUrl}/api/events/commands/${encodeURIComponent(commandId)}`, { signal: this.controller.signal })
    const result = await response.json() as Record<string, unknown>
    if (!response.ok || result.commandId !== commandId || typeof result.httpStatus !== 'number') throw new Error('Command result is unavailable')
    return result
  }
  private async sendCommand(commandId: string, event: string, data: unknown) {
    try {
      const response = await studioFetch(`${this.baseUrl}/api/events/commands`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ commandId, event, data }), signal: this.controller.signal,
      })
      const result = await response.json()
      if (this.controller.signal.aborted) return
      this.dispatch(response.ok && result.success !== false ? 'command_result' : 'command_error', { ...result, commandId })
    } catch (error) {
      if (this.controller.signal.aborted) return
      // Query identity after a lost response; never repeat a possibly-applied action.
      try {
        const result = await this.queryCommand(commandId)
        if (!this.controller.signal.aborted) this.dispatch(Number(result.httpStatus) >= 400 || result.success === false ? 'command_error' : 'command_result', result)
      } catch {
        if (!this.controller.signal.aborted) this.dispatch('command_error', {
          commandId, status: 'unconfirmed', error: error instanceof Error ? error.message : String(error),
        })
      }
    }
  }
  private dispatch(event: string, data?: unknown) {
    for (const handler of this.listeners.get(event) ?? []) handler(...[data] as never[])
  }
  private async listen() {
    if (this.controller.signal.aborted) return
    const connection = new AbortController()
    const abortConnection = () => connection.abort()
    this.controller.signal.addEventListener('abort', abortConnection, { once: true })
    try {
      const response = await studioFetch(`${this.baseUrl}/api/events/stream?afterSeq=${this.sequence}`, { signal: connection.signal })
      if (!response.ok || !response.body) throw new Error('Studio event stream unavailable')
      this.connected = true
      this.dispatch('connect')
      for await (const event of parseServerSentEvents(response.body)) {
        if (this.controller.signal.aborted) return
        const sequence = Number(event.id)
        if (!Number.isSafeInteger(sequence) || sequence < 1) throw new Error('Invalid Studio event sequence')
        if (sequence <= this.sequence) continue
        if (sequence !== this.sequence + 1) throw new Error('Studio event sequence gap; replay required')
        this.dispatch(event.event, JSON.parse(event.data))
        this.sequence = sequence
      }
    } catch (error) {
      if (this.controller.signal.aborted) return
      this.dispatch('connect_error', error)
    } finally {
      connection.abort()
      this.controller.signal.removeEventListener('abort', abortConnection)
    }
    this.connected = false
    this.dispatch('disconnect', 'stream interrupted; awaiting replay')
    if (!this.controller.signal.aborted) this.retry = setTimeout(() => void this.listen(), 1000)
  }
  disconnect() {
    clearTimeout(this.retry)
    this.controller.abort()
    this.connected = false
  }
}
