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
  emit(event: string, data: unknown) {
    void studioFetch(`${this.baseUrl}/api/events/commands`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ commandId: crypto.randomUUID(), event, data }), signal: this.controller.signal,
    }).then(async response => {
      if (!response.ok) this.dispatch('command_error', await response.json())
    }).catch(error => { if (!this.controller.signal.aborted) this.dispatch('command_error', error) })
  }
  private dispatch(event: string, data?: unknown) {
    for (const handler of this.listeners.get(event) ?? []) handler(...[data] as never[])
  }
  private async listen() {
    if (this.controller.signal.aborted) return
    try {
      const response = await studioFetch(`${this.baseUrl}/api/events/stream?afterSeq=${this.sequence}`, { signal: this.controller.signal })
      if (!response.ok || !response.body) throw new Error('Studio event stream unavailable')
      this.connected = true
      this.dispatch('connect')
      for await (const event of parseServerSentEvents(response.body)) {
        if (this.controller.signal.aborted) return
        const sequence = Number(event.id)
        if (!Number.isSafeInteger(sequence) || sequence <= this.sequence) continue
        this.dispatch(event.event, JSON.parse(event.data))
        this.sequence = sequence
      }
    } catch (error) {
      if (this.controller.signal.aborted) return
      this.dispatch('connect_error', error)
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
