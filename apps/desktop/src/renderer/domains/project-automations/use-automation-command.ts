import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import { assertFiniteNumbers, DataCommandNotAccepted } from '../project-data/data-command'
import { createAutomationApi } from './api'
import type { Automation, AutomationUpdate, AutomationWrite } from './types'
import { validateAutomationForm } from './form-schema'
import { safeProjectError, safeProjectFieldErrors } from '../projects/presentation-error'

type Pending = { key: string; body: AutomationWrite | AutomationUpdate; automationId?: string }
type Options = { client: StreamingApiClient; workspaceKey: string; automationId?: string; instanceId: string; disabled: boolean; readOnly: boolean; projectId: string; onSaved(value: Automation, key: string): void }
const storageKey = (options: Options) => `autoflow:automation-command:${JSON.stringify([options.workspaceKey, options.projectId, options.automationId ?? 'new'])}`
function restore(key: string, automationId?: string): Pending | null {
  const serialized = localStorage.getItem(key)
  if (!serialized) return null
  const value = JSON.parse(serialized) as Pending
  if (!value || typeof value.key !== 'string' || value.automationId !== automationId || !value.body || Object.keys(validateAutomationForm(value.body)).length || (automationId && (!('expectedManagementRevision' in value.body) || !Number.isSafeInteger(value.body.expectedManagementRevision)))) throw new Error('保存恢复记录无法读取，请保留当前工作区并检查恢复资料')
  return value
}

/** The containing page is keyed by stable workspace + project + form identity, never instance. */
export function useAutomationCommand(options: Options) {
  const { client, projectId, instanceId, disabled } = options
  const api = useMemo(() => createAutomationApi(client, projectId), [client, projectId])
  const key = storageKey(options)
  const [restored] = useState(() => { try { return { command: restore(key, options.automationId), error: undefined as string | undefined } } catch { return { command: null, error: '无法读取上次保存的恢复资料，已暂停提交。请检查本地存储后重新打开。' } } })
  const scope = useRef(options); scope.current = options
  const pending = useRef<Pending | null>(restored.command), active = useRef(true), ticket = useRef(0), busyRef = useRef(false)
  const [busy, setBusy] = useState(false), [recovering, setRecovering] = useState(Boolean(restored.command)), [notAccepted, setNotAccepted] = useState(false)
  const [error, setError] = useState<string | undefined>(restored.error), [fields, setFields] = useState<Record<string, string>>({}), [conflict, setConflict] = useState(false)
  useLayoutEffect(() => {
    ticket.current++; busyRef.current = false; setBusy(false)
    setRecovering(Boolean(pending.current))
  }, [client, instanceId, disabled])
  useLayoutEffect(() => { active.current = true; return () => { active.current = false; ticket.current++ } }, [])

  const execute = async (mode: 'submit' | 'lookup' | 'retry', body?: AutomationWrite | AutomationUpdate, automationId?: string) => {
    if (restored.error || busyRef.current || scope.current.disabled || (mode !== 'lookup' && scope.current.readOnly)) return
    if ((mode === 'submit' && pending.current) || (mode !== 'submit' && !pending.current) || (mode === 'retry' && !notAccepted)) return
    if (!pending.current) {
      if (!body) return
      try { assertFiniteNumbers(body) } catch { setError('配置含无效数字，本次未提交。'); return }
      const candidate = { key: crypto.randomUUID(), body: structuredClone(body), automationId }
      try { localStorage.setItem(key, JSON.stringify(candidate)) }
      catch { setError('无法保存操作恢复资料，本次未提交。请检查本地存储后重试。'); return }
      pending.current = candidate
    }
    const command = pending.current, attempt = ++ticket.current
    busyRef.current = true; setBusy(true); setError(undefined); setFields({}); setConflict(false)
    const current = () => active.current && ticket.current === attempt && scope.current.client === client && scope.current.instanceId === instanceId && scope.current.projectId === projectId && !scope.current.disabled
    const policy = { canSubmit: () => current() && (mode === 'lookup' || !scope.current.readOnly), lookupOnly: mode === 'lookup', retryIfNotAccepted: false }
    try {
      const saved = command.automationId
        ? await (mode === 'lookup' ? api.resumeUpdate : api.update)(command.automationId, command.body as AutomationUpdate, command.key, policy)
        : await (mode === 'lookup' ? api.resumeCreate : api.create)(command.body, command.key, policy)
      if (!current()) return
      localStorage.removeItem(key); pending.current = null; setRecovering(false); setNotAccepted(false)
      scope.current.onSaved(saved, command.key)
    } catch (failure) {
      if (!current()) return
      setError(safeProjectError(failure))
      if (failure instanceof DataCommandNotAccepted) {
        setNotAccepted(true); setRecovering(true)
      } else if (failure instanceof ApiClientError && failure.status >= 400 && failure.status < 500 && failure.status !== 408) {
        try { localStorage.removeItem(key) } catch { setRecovering(true); setNotAccepted(false); setError('无法清理操作恢复资料，请先核对原请求。'); return }
        pending.current = null; setRecovering(false); setNotAccepted(false)
        setFields(safeProjectFieldErrors(failure.fields)); setConflict(failure.status === 409)
      } else { setRecovering(true); setNotAccepted(false) }
    } finally {
      if (current()) { busyRef.current = false; setBusy(false) }
    }
  }
  return { busy, recovering, notAccepted, error, fields, conflict, restoredCommand: restored.command,
    locked: () => Boolean(restored.error) || busyRef.current || Boolean(pending.current),
    submit: (body: AutomationWrite | AutomationUpdate, automationId?: string) => execute('submit', body, automationId),
    lookup: () => execute('lookup'), retry: () => execute('retry'),
    clearError: () => { if (!pending.current) { setError(undefined); setFields({}); setConflict(false) } },
    discardNotAccepted: () => { if (!busyRef.current && notAccepted) { try { localStorage.removeItem(key) } catch { setError('无法清理操作恢复资料，请检查本地存储后重试。'); return }; pending.current = null; setNotAccepted(false); setRecovering(false); setError(undefined) } },
  }
}
