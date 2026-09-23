import { parseServerSentEvents } from '../../../shared/api/events'
import { studioFetch } from './transport'
import { getStudioOpenContext, scopeStudioUrl } from './config'
import type { components } from '../../../shared/api/generated'

type StudioCommandReceipt = components['schemas']['StudioCommandReceipt']
type StudioCommandLookup = components['schemas']['StudioCommandLookup']

function isCommandReceipt(value: unknown, commandId: string): value is StudioCommandReceipt {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    && 'commandId' in value && typeof value.commandId === 'string' && !!value.commandId.trim()
    && value.commandId === commandId && 'success' in value && typeof value.success === 'boolean'
}

// The source handlers retain their payload types. Only this compatibility boundary is erased.
type Listener = (...args: never[]) => void
export class StudioEventClient {
  connected = false
  private listeners = new Map<string, Set<Listener>>()
  private controller = new AbortController()
  private connection: AbortController | undefined
  private verboseLog: boolean
  private sequence = 0
  private retry: ReturnType<typeof setTimeout> | undefined
  private readonly projectId = getStudioOpenContext().projectId
  constructor(private baseUrl: string, options: { verboseLog?: boolean } = {}) {
    this.verboseLog = options.verboseLog ?? true
    queueMicrotask(() => void this.listen())
  }
  setVerboseLog(enabled: boolean) {
    if (this.verboseLog === enabled || this.controller.signal.aborted) return
    this.verboseLog = enabled
    // Change only this stream; keep acknowledged cursor and in-flight commands.
    this.connection?.abort()
  }
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
  emit(event: string, data: unknown, commandId: string = crypto.randomUUID()) {
    void this.sendCommand(commandId, event, data)
    return commandId
  }
  command(event: string, data: unknown, commandId: string = crypto.randomUUID()): Promise<StudioCommandReceipt> {
    return this.sendCommand(commandId, event, data)
  }
  async queryCommand(commandId: string): Promise<StudioCommandLookup> {
    const response = await studioFetch(scopeStudioUrl(`${this.baseUrl}/api/events/commands/${encodeURIComponent(commandId)}`, this.projectId), { signal: this.controller.signal })
    const result: unknown = await response.json()
    if (!response.ok || !isCommandReceipt(result, commandId)
      || typeof result.httpStatus !== 'number' || !Number.isInteger(result.httpStatus) || result.httpStatus < 200 || result.httpStatus > 599) {
      throw new Error('命令查询结果无效或身份不匹配')
    }
    return result as StudioCommandLookup
  }
  private async sendCommand(commandId: string, event: string, data: unknown): Promise<StudioCommandReceipt> {
    const interrupted = { commandId, success: false, status: 'unconfirmed', error: '连接已中断，命令结果尚未确认' }
    try {
      const response = await studioFetch(scopeStudioUrl(`${this.baseUrl}/api/events/commands`, this.projectId), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ commandId, event, data }), signal: this.controller.signal,
      })
      const result: unknown = await response.json()
      if (this.controller.signal.aborted) return interrupted
      if (!response.ok) {
        // A server/gateway failure may occur after application. Resolve the original identity.
        const record = typeof result === 'object' && result !== null ? result : null
        if (response.status >= 500 || (record && 'commandId' in record && record.commandId !== commandId)
          || (record && 'success' in record && record.success === true)) {
          throw new Error(`HTTP ${response.status}: 命令结果需要查询确认`)
        }
        const rejected = { ...(typeof result === 'object' && result !== null ? result : {}), commandId, success: false }
        this.dispatch('command_error', rejected)
        return rejected
      }
      if (!isCommandReceipt(result, commandId)) throw new Error('命令响应无效或身份不匹配')
      this.dispatch(result.success ? 'command_result' : 'command_error', result)
      return result
    } catch (error) {
      if (this.controller.signal.aborted) return interrupted
      // Query identity after a lost response; never repeat a possibly-applied action.
      try {
        const result = await this.queryCommand(commandId)
        if (this.controller.signal.aborted) return interrupted
        const confirmed = { ...result, success: result.success && result.httpStatus < 400 }
        this.dispatch(confirmed.success ? 'command_result' : 'command_error', confirmed)
        return confirmed
      } catch {
        const unconfirmed = { commandId, success: false, status: 'unconfirmed', error: error instanceof Error ? error.message : String(error) }
        if (!this.controller.signal.aborted) this.dispatch('command_error', unconfirmed)
        return unconfirmed
      }
    }
  }
  private dispatch(event: string, data?: unknown) {
    // UI subscriber failures are not transport failures: replaying would duplicate already-applied effects.
    for (const handler of [...(this.listeners.get(event) ?? [])]) {
      try { handler(...[data] as never[]) }
      catch (error) { console.error('[Studio events] subscriber failed', event, error) }
    }
  }
  private async listen() {
    if (this.controller.signal.aborted) return
    const connection = new AbortController()
    this.connection = connection
    const verboseLog = this.verboseLog
    const abortConnection = () => connection.abort()
    this.controller.signal.addEventListener('abort', abortConnection, { once: true })
    try {
      const query = new URLSearchParams({ afterSeq: String(this.sequence), verboseLog: String(verboseLog) })
      if (this.projectId) query.set('projectId', this.projectId)
      const response = await studioFetch(`${this.baseUrl}/api/events/stream?${query}`, { signal: connection.signal })
      if (!response.ok || !response.body) {
        if (response.status === 409) {
          const payload: unknown = await response.json().catch(() => null)
          if (payload && typeof payload === 'object' && !Array.isArray(payload)
            && 'error' in payload && payload.error && typeof payload.error === 'object' && !Array.isArray(payload.error)
            && 'code' in payload.error && payload.error.code === 'EVENT_CURSOR_AHEAD') this.sequence = 0
        }
        throw new Error('Studio event stream unavailable')
      }
      this.connected = true
      this.dispatch('connect')
      for await (const event of parseServerSentEvents(response.body)) {
        if (this.controller.signal.aborted) return
        if (connection.signal.aborted) break
        const sequence = Number(event.id)
        if (!Number.isSafeInteger(sequence) || sequence < 1) throw new Error('Invalid Studio event sequence')
        if (sequence <= this.sequence) continue
        if (sequence !== this.sequence + 1) throw new Error('Studio event sequence gap; replay required')
        this.dispatch(event.event, JSON.parse(event.data))
        this.sequence = sequence
      }
    } catch (error) {
      if (this.controller.signal.aborted) return
      if (verboseLog === this.verboseLog) this.dispatch('connect_error', error)
    } finally {
      connection.abort()
      this.connection = undefined
      this.controller.signal.removeEventListener('abort', abortConnection)
    }
    this.connected = false
    this.dispatch('disconnect', 'stream interrupted; awaiting replay')
    if (!this.controller.signal.aborted) this.retry = setTimeout(() => void this.listen(), verboseLog === this.verboseLog ? 1000 : 0)
  }
  disconnect() {
    clearTimeout(this.retry)
    this.controller.abort()
    this.connected = false
  }
}
