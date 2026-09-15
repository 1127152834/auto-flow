import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import { DataCommandNotAccepted } from '../project-data/data-command'
import { createProjectRunsApi, type Batch, type BatchQuery, type BatchStartRequest, type BatchStopRequest, type RunOperation, type TaskQuery } from './api'
import { presentRunFailure } from './presentation'

export const runQueryKeys = {
  batches: (workspaceKey: string, instanceId: string, projectId: string, filter: BatchQuery) => [workspaceKey, instanceId, 'project-runs', projectId, 'batches', filter] as const,
  batch: (workspaceKey: string, instanceId: string, projectId: string, batchId: string) => [workspaceKey, instanceId, 'project-runs', projectId, 'batch', batchId] as const,
  tasks: (workspaceKey: string, instanceId: string, projectId: string, filter: TaskQuery) => [workspaceKey, instanceId, 'project-runs', projectId, 'tasks', filter] as const,
  task: (workspaceKey: string, instanceId: string, projectId: string, taskId: string) => [workspaceKey, instanceId, 'project-runs', projectId, 'task', taskId] as const,
}
type Action = { type: 'start'; automationId: string; body: BatchStartRequest } | { type: 'stop' | 'forceStop'; batchId: string; body: BatchStopRequest }
type Pending = Action & { key: string }
type CommandScope = { type: 'start'; automationId: string } | { type: 'stop'; batchId: string }
type Options = { client: StreamingApiClient; workspaceKey: string; instanceId: string; projectId: string; scope: CommandScope; disabled: boolean; readOnly: boolean; onAccepted?(operation: RunOperation, key: string): boolean | void; onCompleted(batch: Batch, key: string): void }
const storageKey = ({ workspaceKey, projectId, scope }: Options) => `autoflow:project-run-command:${JSON.stringify([workspaceKey, projectId, scope.type, scope.type === 'start' ? scope.automationId : scope.batchId])}`
const inScope = (action: Action, scope: CommandScope) => scope.type === 'start' ? action.type === 'start' && action.automationId === scope.automationId : action.type !== 'start' && action.batchId === scope.batchId
const object = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value)
const scalar = (value: unknown) => value === null || typeof value === 'string' || typeof value === 'boolean' || typeof value === 'number' && Number.isFinite(value)
function readPending(key: string, scope: CommandScope): { value: Pending | null; error?: string } {
  try {
    const serialized = localStorage.getItem(key); if (!serialized) return { value: null }
    const value: unknown = JSON.parse(serialized)
    if (!object(value) || typeof value.key !== 'string' || !value.key || !object(value.body)) throw new Error()
    if (value.type === 'start' && typeof value.automationId === 'string' && Number.isSafeInteger(value.body.expectedAutomationRevision) && object(value.body.parameters) && Object.values(value.body.parameters).every(scalar)) { const pending = value as unknown as Pending; if (inScope(pending, scope)) return { value: pending } }
    if ((value.type === 'stop' || value.type === 'forceStop') && typeof value.batchId === 'string' && Number.isSafeInteger(value.body.expectedStatusRevision) && typeof value.body.reason === 'string') { const pending = value as unknown as Pending; if (inScope(pending, scope)) return { value: pending } }
  } catch { /* Invalid recovery data is never submitted. */ }
  return { value: null, error: '无法读取批次操作恢复资料，已暂停提交' }
}

export function useBatchCommand(options: Options) {
  const { client, workspaceKey, instanceId, projectId, disabled } = options, api = useMemo(() => createProjectRunsApi(client, projectId), [client, projectId]), store = storageKey(options)
  const [initial] = useState(() => readPending(store, options.scope))
  const pending = useRef(initial.value), scope = useRef(options), ticket = useRef(0), active = useRef(false), busyRef = useRef(false), acceptedKey = useRef<string | null>(null); scope.current = options
  const [restoredCommand, setRestoredCommand] = useState(initial.value), [busy, setBusy] = useState(false), [recovering, setRecovering] = useState(Boolean(initial.value)), [notAccepted, setNotAccepted] = useState(false), [error, setError] = useState<string | undefined>(initial.error), [invalidRecovery, setInvalidRecovery] = useState(Boolean(initial.error))
  useLayoutEffect(() => { const restored = readPending(store, scope.current.scope); ticket.current += 1; busyRef.current = false; acceptedKey.current = null; pending.current = restored.value; setRestoredCommand(restored.value); setBusy(false); setRecovering(Boolean(restored.value)); setNotAccepted(false); setError(restored.error); setInvalidRecovery(Boolean(restored.error)) }, [store])
  useLayoutEffect(() => { ticket.current += 1; busyRef.current = false; setBusy(false); setRecovering(Boolean(pending.current)) }, [client, instanceId, disabled])
  useLayoutEffect(() => { active.current = true; return () => { active.current = false; ticket.current += 1 } }, [])
  const clear = () => { try { localStorage.removeItem(store) } catch { setError('无法清理批次操作恢复资料'); return false }; acceptedKey.current = null; pending.current = null; setRestoredCommand(null); setRecovering(false); setNotAccepted(false); setInvalidRecovery(false); setError(undefined); return true }
  const execute = async (mode: 'submit' | 'lookup' | 'retry', action?: Action) => {
    const candidateAction = action ?? pending.current
    if (invalidRecovery || busyRef.current || disabled || (candidateAction && !inScope(candidateAction, scope.current.scope)) || (mode !== 'lookup' && candidateAction?.type === 'start' && scope.current.readOnly) || (mode === 'submit' && pending.current) || (mode !== 'submit' && !pending.current)) return
    if (!pending.current && action) { const next = { ...structuredClone(action), key: crypto.randomUUID() }; try { localStorage.setItem(store, JSON.stringify(next)) } catch { setError('无法保存启动恢复资料，本次未提交'); return }; pending.current = next }
    const command = pending.current; if (!command) return
    const attempt = ++ticket.current; busyRef.current = true; setBusy(true); setError(undefined)
    const current = () => active.current && ticket.current === attempt && scope.current.client === client && scope.current.workspaceKey === workspaceKey && scope.current.instanceId === instanceId && scope.current.projectId === projectId && storageKey(scope.current) === store && !scope.current.disabled
    const policy = { canSubmit: () => current() && (command.type !== 'start' || !scope.current.readOnly), lookupOnly: mode === 'lookup', retryIfNotAccepted: mode === 'retry' }
    try {
      const outcome = command.type === 'start' ? await (mode === 'submit' ? api.start : api.resumeStart)(command.automationId, command.body, command.key, policy) : command.type === 'stop' ? await (mode === 'submit' ? api.stop : api.resumeStop)(command.batchId, command.body, command.key, policy) : await (mode === 'submit' ? api.forceStop : api.resumeForceStop)(command.batchId, command.body, command.key, policy)
      if (!current()) return
      if (outcome.state === 'accepted') { acceptedKey.current = command.key; setRecovering(true); setNotAccepted(false); if (scope.current.onAccepted?.(outcome.operation, command.key) === true && acceptedKey.current === pending.current?.key) clear(); return }
      localStorage.removeItem(store); pending.current = null; setRecovering(false); setNotAccepted(false); scope.current.onCompleted(outcome.batch, command.key)
    } catch (failure) {
      if (!current()) return; setError(presentRunFailure(failure, '批次操作结果尚未确认，请核对原操作'))
      if (failure instanceof DataCommandNotAccepted) { setRecovering(true); setNotAccepted(true) }
      else if (failure instanceof ApiClientError && failure.status >= 400 && failure.status < 500 && failure.status !== 408) { localStorage.removeItem(store); pending.current = null; setRecovering(false) }
      else setRecovering(true)
    } finally { if (current()) { busyRef.current = false; setBusy(false) } }
  }
  const discard = () => { if (!busyRef.current) clear() }
  return { busy, recovering, notAccepted, invalidRecovery, error, restoredCommand, locked: () => invalidRecovery || busyRef.current || Boolean(pending.current), start: (automationId: string, body: BatchStartRequest) => execute('submit', { type: 'start', automationId, body }), stop: (batchId: string, body: BatchStopRequest) => execute('submit', { type: 'stop', batchId, body }), forceStop: (batchId: string, body: BatchStopRequest) => execute('submit', { type: 'forceStop', batchId, body }), lookup: () => execute('lookup'), retry: () => execute('retry'), acknowledgeAccepted: () => { if (acceptedKey.current && acceptedKey.current === pending.current?.key) clear() }, discardNotAccepted: () => { if (notAccepted) discard() }, discardInvalidRecovery: () => { if (invalidRecovery) discard() } }
}
