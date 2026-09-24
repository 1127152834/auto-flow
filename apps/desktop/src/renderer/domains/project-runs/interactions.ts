import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import { nativePathSelection } from '../workflows/lib/nativePathSelection'
import { checkedPathSelection } from '../workflows/lib/pathSelectionContract'
import { runJsScript } from '../workflows/lib/runJsScript'

type Schema = components['schemas']
export type InteractionIdentity = Schema['ProjectInteractionIdentity']
export type InteractionRequest = Schema['ProjectInputPromptRequest'] | Schema['ProjectJsScriptRequest'] | Schema['ProjectInteractionClosed']
type Receipt = Schema['ProjectInteractionReceipt']
type Command = Schema['ProjectInteractionCommand']
const transient = (error: unknown) => error instanceof TypeError || error instanceof DOMException && error.name === 'TimeoutError' || error instanceof ApiClientError && (error.status >= 500 || error.status === 408)
const root = (target: InteractionIdentity) => `/api/v1/projects/${encodeURIComponent(target.projectId)}/tasks/${encodeURIComponent(target.taskId)}/interactions`
export function createProjectInteractions(client: () => StreamingApiClient) {
  const checked = (receipt: Receipt, target: InteractionIdentity, commandId: string) => {
    if (receipt.commandId !== commandId || receipt.requestId !== target.requestId || !['accepted', 'applied', 'unconfirmed'].includes(receipt.status)) throw new Error('交互命令回执与当前请求不符')
    return receipt
  }
  const command = async (target: InteractionIdentity, commandId: string, signal?: AbortSignal) => checked(await client().request<Receipt>(`${root(target)}/commands/${encodeURIComponent(commandId)}`, { signal }), target, commandId)
  return {
    pending: (signal?: AbortSignal) => client().request<InteractionIdentity[]>('/api/v1/project-run-interactions', { signal }),
    async request(target: InteractionIdentity, signal?: AbortSignal) {
      const data = await client().request<InteractionRequest>(`${root(target)}/requests/${encodeURIComponent(target.requestId)}`, { signal })
      if (data.requestId !== target.requestId || data.status !== 'cancelled' && (data.runId !== target.runId || data.executionGeneration !== target.executionGeneration || data.type !== target.type)) throw new Error('交互请求与当前运行不符')
      return data
    },
    command,
    async submit(target: InteractionIdentity, commandId: string, event: Command['event'], data: Command['data'], signal?: AbortSignal) {
      signal?.throwIfAborted()
      try {
        return checked(await client().request<Receipt>(`${root(target)}/commands`, { method: 'POST', body: { commandId, executionGeneration: target.executionGeneration, event, data }, signal }), target, commandId)
      } catch (error) {
        signal?.throwIfAborted()
        if (!transient(error)) throw error
        // Query this identity after an unknown response; never replay an action.
        return command(target, commandId, signal)
      }
    },
    async selectPath(kind: 'file' | 'folder', title?: string) {
      if (window.autoflow?.chooseWorkflowPath) return nativePathSelection({ kind, title })
      try { return checkedPathSelection({ success: true, data: await client().request(`/api/system/select-${kind}`, { method: 'POST', body: { title } }) }) }
      catch { return { success: false, error: '路径选择失败，请重试' } }
    },
  }
}
export type ProjectInteractionsApi = ReturnType<typeof createProjectInteractions>
function pause(signal: AbortSignal) {
  return new Promise<void>(resolve => {
    if (signal.aborted) { resolve(); return }
    const done = () => { clearTimeout(timer); signal.removeEventListener('abort', done); resolve() }
    const timer = setTimeout(done, 500)
    signal.addEventListener('abort', done, { once: true })
  })
}
// Source behavior: claim -> original dedicated JS Worker -> confirmed result.
// A renderer that reconnects after losing its claim cannot replay the script.
export async function executeProjectScript(api: ProjectInteractionsApi, target: InteractionIdentity, signal: AbortSignal) {
  const data = await api.request(target, signal)
  signal.throwIfAborted()
  if (data.status === 'cancelled') return
  if (data.type !== 'execution:js_script' || data.status !== 'pending') throw new Error('脚本已被领取，无法安全重放；请停止本次运行')
  const confirm = async (event: Command['event'], payload: Command['data']) => {
    const commandId = crypto.randomUUID()
    let receipt: Receipt | undefined
    try { receipt = await api.submit(target, commandId, event, payload, signal) }
    catch (error) { if (!transient(error)) throw error }
    while (!signal.aborted) {
      if (receipt?.status === 'applied') return
      if (receipt?.status === 'unconfirmed') throw new Error('脚本命令未被确认，不会重新执行')
      await pause(signal)
      signal.throwIfAborted()
      try { receipt = await api.command(target, commandId, signal) }
      catch (error) { if (!transient(error)) throw error }
    }
    signal.throwIfAborted()
  }
  const claimId = crypto.randomUUID()
  await confirm('js_script_claim', { requestId: target.requestId, claimId })
  signal.throwIfAborted()
  const result = await runJsScript(data.code, data.variables, signal)
  signal.throwIfAborted()
  await confirm('js_script_result', { ...result, requestId: target.requestId, claimId })
}
