import { encodeRecordKey } from './record-route'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { StreamingApiClient } from '../../shared/api/client'
import { ApiClientError } from '../../shared/api/client'
import type { components } from '../../shared/api/generated'
import { createDataCatalogApi, type CatalogScope } from './catalog-api'
import { assertFiniteNumbers, DataCommandNotAccepted, DataCommandUncertain, type DataCommandPolicy } from './data-command'
import { createProjectDataApi } from './api'
import { createRecordsApi, type RecordKey } from './records-api'
import { createSchemaApi } from './schema-api'
import { statusFormSchema } from './status-form-schema'
import type { FieldSubmission } from './components/FieldEditorDialog'
import type { StatusSubmission } from './components/StatusEditorDialog'
import { safeProjectError } from '../projects/presentation-error'

type Schema = components['schemas']
type Scope = CatalogScope & { workspaceKey: string }

export type EditingContext = {
  scope: Scope
  table: Schema['DataTableView']
  fields: Schema['DataFieldDirectory']
  statuses: Schema['DataStatusDirectory']
}

export type DataEditor = EditingContext & { session: string; submittedValues?: Schema['DataCellWrite'][]; submittedSchema?: Schema['DataSchemaCandidate'] } & (
  | { kind: 'tableEdit' }
  | { kind: 'recordCreate' }
  | { kind: 'recordEdit' | 'recordStatus' | 'recordDelete'; record: Schema['DataRecordView'] }
  | { kind: 'fieldCreate' }
  | { kind: 'fieldEdit'; field: Schema['DataFieldView'] }
  | { kind: 'statusCreate' }
  | { kind: 'statusEdit' | 'statusDelete'; status: Schema['DataStatusView'] }
  | { kind: 'schemaSave' }
)

type EditorInput =
  | { kind: 'tableEdit' }
  | { kind: 'recordCreate' }
  | { kind: 'recordEdit' | 'recordStatus' | 'recordDelete'; record: Schema['DataRecordView'] }
  | { kind: 'fieldCreate' }
  | { kind: 'fieldEdit'; field: Schema['DataFieldView'] }
  | { kind: 'statusCreate' }
  | { kind: 'statusEdit' | 'statusDelete'; status: Schema['DataStatusView'] }
  | { kind: 'schemaSave' }

type Pending = { key: string; scope: Scope; session: string } & (
  | { kind: 'tableEdit'; body: Schema['DataTablePatch'] }
  | { kind: 'recordCreate'; body: Omit<Schema['DataRecordCreate'], 'datasetGeneration'> }
  | { kind: 'recordEdit'; target: RecordKey; body: Omit<Schema['DataRecordPatch'], 'datasetGeneration' | 'recordKeyType'> }
  | { kind: 'recordStatus'; target: RecordKey; body: Omit<Schema['DataRecordStatusWrite'], 'datasetGeneration' | 'recordKeyType'> }
  | { kind: 'recordDelete'; target: RecordKey; body: Omit<Schema['RecordDelete'], 'datasetGeneration' | 'recordKeyType'> }
  | { kind: 'fieldCreate'; body: Schema['DataFieldCreate'] }
  | { kind: 'fieldEdit'; target: string; body: Schema['DataFieldPatch'] }
  | { kind: 'statusCreate'; body: Schema['DataStatusCreate'] }
  | { kind: 'statusEdit'; target: string; body: Schema['DataStatusPatch'] }
  | { kind: 'statusDelete'; target: string; body: Schema['StatusDelete'] }
  | { kind: 'schemaSave'; body: Schema['DataSchemaCommit'] }
)

type Impact = Schema['DeletionImpactReport'] | Schema['FieldImpactReport']
type Options = { workspaceKey: string; context: EditingContext | null; client: StreamingApiClient; instanceId: string; disabled: boolean; readonly: boolean; onSaved(kind: Pending['kind'], operationKey: string, result: unknown): void }
type Live = Options & { mounted: boolean }

const clone = <T,>(value: T): T => structuredClone(value)
const sameScope = (a: Scope, b: Scope) => a.workspaceKey === b.workspaceKey && a.projectId === b.projectId && a.tableId === b.tableId && a.datasetGeneration === b.datasetGeneration
const sameTable = (a: Scope, b: Scope) => a.workspaceKey === b.workspaceKey && a.projectId === b.projectId && a.tableId === b.tableId
const storageKey = (scope: Scope) => `autoflow:data-edit:${encodeURIComponent(scope.workspaceKey)}:${encodeURIComponent(scope.projectId)}:${encodeURIComponent(scope.tableId)}`
const message = safeProjectError
const object = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value)
const only = (value: Record<string, unknown>, required: string[], optional: string[] = []) => required.every(key => key in value) && Object.keys(value).every(key => required.includes(key) || optional.includes(key))
const kinds = new Set<Pending['kind']>(['tableEdit', 'recordCreate', 'recordEdit', 'recordStatus', 'recordDelete', 'fieldCreate', 'fieldEdit', 'statusCreate', 'statusEdit', 'statusDelete', 'schemaSave'])
const validScope = (value: unknown): value is Scope => object(value) && ['workspaceKey', 'projectId', 'tableId', 'datasetGeneration'].every(key => typeof value[key] === 'string' && value[key].length > 0)
const validTarget = (value: unknown, kind: Pending['kind']) => {
  if (kind === 'recordEdit' || kind === 'recordStatus' || kind === 'recordDelete') {
    if (!object(value) || !['text', 'integer', 'uuid'].includes(String(value.type)) || typeof value.value !== 'string') return false
    try { encodeRecordKey(value as RecordKey); return true } catch { return false }
  }
  if (kind === 'fieldEdit' || kind === 'statusEdit' || kind === 'statusDelete') return typeof value === 'string' && value.length > 0
  return value === undefined
}
const validScalar = (value: unknown) => value === null || typeof value === 'string' || typeof value === 'boolean' || typeof value === 'number' && Number.isFinite(value) || object(value) && value.kind === 'date' && ['date', 'datetime'].includes(String(value.precision)) && typeof value.value === 'string' && (value.offset === null || value.offset === undefined || typeof value.offset === 'string')
const validSchemaScalar = (value: unknown) => value === null || typeof value === 'string' || typeof value === 'boolean' || typeof value === 'number' && Number.isFinite(value) || object(value) && only(value, ['kind', 'precision', 'value', 'offset']) && value.kind === 'date' && ['date', 'datetime'].includes(String(value.precision)) && typeof value.value === 'string' && (value.offset === null || typeof value.offset === 'string')
const validCellWrites = (value: unknown) => Array.isArray(value) && value.every(cell => object(cell) && typeof cell.fieldId === 'string' && cell.fieldId.length > 0 && validScalar(cell.value));
const validJson = (value: unknown): boolean => value === null || typeof value === 'boolean' || typeof value === 'string' || typeof value === 'number' && Number.isFinite(value) || Array.isArray(value) && value.every(validJson) || object(value) && Object.values(value).every(validJson)
const validDefinition = (value: unknown) => object(value) && only(value, ['key', 'name', 'type', 'required', 'validation']) && typeof value.key === 'string' && value.key.length > 0 && typeof value.name === 'string' && value.name.length > 0 && ['string', 'number', 'boolean', 'date'].includes(String(value.type)) && typeof value.required === 'boolean' && object(value.validation) && validJson(value.validation)
const validFieldDirectory = (value: unknown, scope: Scope) => object(value) && Number.isSafeInteger(value.tableRevision) && Number(value.tableRevision) > 0 && Array.isArray(value.items) && value.items.every(field => {
  if (!object(field) || !object(field.ref)) return false
  const definition = { key: field.key, name: field.name, type: field.type, required: field.required, validation: field.validation }
  return validDefinition(definition) && typeof field.writable === 'boolean' && typeof field.formula === 'boolean' && Number.isSafeInteger(field.fieldRevision) && Number(field.fieldRevision) > 0 && typeof field.ref.fieldId === 'string' && field.ref.fieldId.length > 0 && field.ref.projectId === scope.projectId && field.ref.tableId === scope.tableId && field.ref.datasetGeneration === scope.datasetGeneration
})
const validSchemaCandidate = (value: unknown): value is Schema['DataSchemaCandidate'] => object(value) && only(value, ['datasetGeneration', 'expectedTableRevision', 'fields']) && typeof value.datasetGeneration === 'string' && value.datasetGeneration.length > 0 && Number.isSafeInteger(value.expectedTableRevision) && Number(value.expectedTableRevision) > 0 && Array.isArray(value.fields) && value.fields.every(field => {
  if (!object(field) || !validDefinition(field.definition)) return false
  if (field.kind === 'existing') return only(field, ['kind', 'fieldId', 'expectedFieldRevision', 'definition']) && typeof field.fieldId === 'string' && field.fieldId.length > 0 && Number.isSafeInteger(field.expectedFieldRevision) && Number(field.expectedFieldRevision) > 0
  return field.kind === 'new' && only(field, ['kind', 'clientId', 'definition', 'sourceColumnPolicy'], ['existingRecordDefault']) && typeof field.clientId === 'string' && field.clientId.length > 0 && field.sourceColumnPolicy === 'localOnly' && (!('existingRecordDefault' in field) || validSchemaScalar(field.existingRecordDefault))
})
const restored = (value: unknown, current: Scope): { pending: Pending; editor: DataEditor } | null => {
  if (!object(value) || !object(value.pending) || !object(value.editor)) return null
  const pending = value.pending, editor = value.editor
  if ((pending.kind === 'recordCreate' || pending.kind === 'recordEdit') && (!object(pending.body) || !validCellWrites(pending.body.values))) return null
  if (pending.kind === 'schemaSave' && (!object(pending.body) || !validSchemaCandidate(pending.body.candidate) || !Number.isSafeInteger(pending.body.impactRevision) || !validSchemaCandidate(editor.submittedSchema) || !sameValue(pending.body.candidate, editor.submittedSchema))) return null
  if (typeof pending.kind !== 'string' || !kinds.has(pending.kind as Pending['kind']) || pending.kind !== editor.kind || typeof pending.key !== 'string' || !pending.key || typeof pending.session !== 'string' || !pending.session || pending.session !== editor.session || !validScope(pending.scope) || !validScope(editor.scope) || !sameTable(pending.scope, current) || !sameScope(pending.scope, editor.scope) || !object(pending.body) || !validTarget(pending.target, pending.kind as Pending['kind']) || !object(editor.table) || !object(editor.fields) || !object(editor.statuses)) return null
  if (pending.kind === 'schemaSave') {
    const body = pending.body as Schema['DataSchemaCommit']
    if (!validFieldDirectory(editor.fields, pending.scope) || body.candidate.datasetGeneration !== pending.scope.datasetGeneration || body.candidate.expectedTableRevision !== editor.fields.tableRevision) return null
  }
  return { pending: pending as Pending, editor: editor as DataEditor }
}

function dispatch(client: StreamingApiClient, pending: Pending, resume: boolean, policy: DataCommandPolicy) {
  const tables = createProjectDataApi(client, pending.scope.projectId)
  const catalog = createDataCatalogApi(client, pending.scope)
  const records = createRecordsApi(client, pending.scope)
  const schema = createSchemaApi(client, pending.scope)
  switch (pending.kind) {
    case 'tableEdit': return resume ? tables.resumePatch(pending.scope.tableId, pending.body, pending.key, policy) : tables.patch(pending.scope.tableId, pending.body, pending.key, policy)
    case 'recordCreate': return records.create(pending.body, pending.key, resume, policy)
    case 'recordEdit': return records.update(pending.target, pending.body, pending.key, resume, policy)
    case 'recordStatus': return records.setStatus(pending.target, pending.body, pending.key, resume, policy)
    case 'recordDelete': return records.delete(pending.target, pending.body, pending.key, resume, policy)
    case 'fieldCreate': return catalog.createField(pending.body, pending.key, resume, policy)
    case 'fieldEdit': return catalog.updateField(pending.target, pending.body, pending.key, resume, policy)
    case 'statusCreate': return catalog.createStatus(pending.body, pending.key, resume, policy)
    case 'statusEdit': return catalog.updateStatus(pending.target, pending.body, pending.key, resume, policy)
    case 'statusDelete': return catalog.deleteStatus(pending.target, pending.body, pending.key, resume, policy)
    case 'schemaSave': return schema.commit(pending.body, pending.key, resume, policy)
    default: throw new Error('不支持的保存恢复类型')
  }
}

const sameValue = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

export function useDataTableEditing(options: Options) {
  const [editor, setEditor] = useState<DataEditor | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [dialogSaving, setDialogSaving] = useState(false)
  const [recoveryPending, setRecoveryPending] = useState(false)
  const [notAccepted, setNotAccepted] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [recoveryBlocked, setRecoveryBlocked] = useState(false)
  const [impact, setImpact] = useState<Schema['DeletionImpactReport'] | null>(null)
  const fieldImpact = useRef<Schema['FieldImpactReport'] | null>(null)
  const schemaPreview = useRef<{ candidate: Schema['DataSchemaCandidate']; impact: Schema['DataSchemaImpact'] } | null>(null)
  const pending = useRef<Pending | null>(null)
  const lock = useRef(false), epoch = useRef(0), ticket = useRef(0), dirty = useRef(false)
  const activeSession = useRef<string | null>(null)
  const dialogBusy = useRef<{ session: string; value: boolean } | null>(null)
  const loadedStorageKey = useRef<string | null>(null)
  const live = useRef<Live>({ ...options, mounted: true })

  useLayoutEffect(() => {
    const previous = live.current
    const contextChanged = Boolean(previous.context && options.context && !sameScope(previous.context.scope, options.context.scope)) || Boolean(previous.context) !== Boolean(options.context)
    const authorityChanged = previous.workspaceKey !== options.workspaceKey || previous.client !== options.client || previous.instanceId !== options.instanceId || previous.disabled !== options.disabled
    live.current = { ...options, mounted: true }
    if (contextChanged || authorityChanged) {
      epoch.current += 1
      lock.current = false
      schemaPreview.current = null
      setBusy(false)
      if (pending.current) setRecoveryPending(true)
    }
    const key = options.context ? storageKey(options.context.scope) : null
    if (key !== loadedStorageKey.current) {
      loadedStorageKey.current = key
      setRecoveryBlocked(false)
      if (key && !pending.current && !editor) try {
        const raw = localStorage.getItem(key)
        if (raw) {
          const saved = restored(JSON.parse(raw), options.context!.scope)
          if (!saved) throw new Error('保存恢复记录不完整，已阻止新的写入。')
          pending.current = clone(saved.pending); activeSession.current = saved.editor.session
          setEditor({ ...clone(saved.editor), ...((saved.pending.kind === 'recordCreate' || saved.pending.kind === 'recordEdit') ? { submittedValues: clone((saved.pending.body as { values: Schema['DataCellWrite'][] }).values) } : {}) }); setRecoveryPending(true); setError('上次保存结果尚未确认，请先核对原请求。')
        }
      } catch { setRecoveryBlocked(true); setError('保存恢复记录不完整，已阻止新的写入。') }
    }
  }, [options.client, options.context, options.disabled, options.instanceId, options.onSaved, options.readonly, options.workspaceKey])
  useEffect(() => () => { live.current.mounted = false; epoch.current += 1; lock.current = false }, [])

  const current = (run: number, session: string, usedClient: StreamingApiClient, usedInstance: string) => {
    const value = live.current
    return value.mounted && run === epoch.current && activeSession.current === session && value.client === usedClient && value.instanceId === usedInstance && !value.disabled
  }

  const clearFlags = () => { setError(null); setNotAccepted(false); setConflict(false) }
  const clearStored = (command: Pending) => {
    if (pending.current?.key === command.key) try {
      const key = storageKey(command.scope), raw = localStorage.getItem(key), saved = raw ? JSON.parse(raw) : null
      if (object(saved) && object(saved.pending) && saved.pending.key === command.key) localStorage.removeItem(key)
    }
    catch (caught) { setError(`保存结果已确认，但无法清除本地恢复记录：${message(caught)}`) }
  }
  const requireEditor = () => {
    if (!editor) throw new Error('没有打开的编辑会话')
    return editor
  }
  const writable = () => {
    const value = live.current
    if (!value.context || value.disabled || value.readonly) throw new Error('当前上下文不可写')
  }

  const execute = useCallback(async (mode: 'submit' | 'recover' | 'retry') => {
    const command = pending.current
    if (!command) throw new Error('没有待核对的保存请求')
    if (lock.current) throw new Error('保存请求正在处理')
    if (mode === 'recover' && live.current.workspaceKey !== command.scope.workspaceKey) {
      const mismatch = new Error('请返回原工作区后核对保存结果')
      setRecoveryPending(true); setError(safeProjectError(mismatch))
      throw mismatch
    }
    if (mode !== 'recover') writable()
    lock.current = true; setBusy(true); clearFlags()
    const run = epoch.current, usedClient = live.current.client, usedInstance = live.current.instanceId, runTicket = ++ticket.current
    const isCurrent = () => runTicket === ticket.current && current(run, command.session, usedClient, usedInstance)
    try {
      const policy: DataCommandPolicy = {
        lookupOnly: mode === 'recover',
        canSubmit: () => isCurrent() && !live.current.readonly && !live.current.disabled && Boolean(live.current.context && sameScope(live.current.context.scope, command.scope)),
      }
      const value = await dispatch(usedClient, command, mode === 'recover', policy)
      if (!isCurrent()) return value
      if (!live.current.context || !sameScope(live.current.context.scope, command.scope)) {
        clearStored(command)
        pending.current = null; setRecoveryPending(false); setNotAccepted(false)
        setError('原数据范围的保存已确认；请载入当前数据范围后继续。')
        return value
      }
      clearStored(command)
      pending.current = null; setRecoveryPending(false); setNotAccepted(false); setImpact(null); fieldImpact.current = null; schemaPreview.current = null; setEditor(null)
      activeSession.current = null; dialogBusy.current = null; setDialogSaving(false)
      live.current.onSaved(command.kind, command.key, value)
      return value
    } catch (caught) {
      if (!isCurrent()) return undefined
      if (caught instanceof DataCommandNotAccepted) { setNotAccepted(true); setRecoveryPending(true); setError(safeProjectError(caught)); throw caught }
      if (caught instanceof DataCommandUncertain) { setRecoveryPending(true); setError(safeProjectError(caught)); throw caught }
      clearStored(command); pending.current = null; setRecoveryPending(false)
      if (caught instanceof ApiClientError && caught.status === 409 && caught.code === 'REVISION_CONFLICT') setConflict(true)
      if (caught instanceof ApiClientError && caught.status === 412) { setImpact(null); fieldImpact.current = null; schemaPreview.current = null }
      setError(message(caught)); throw caught
    } finally {
      if (runTicket === ticket.current && run === epoch.current) { lock.current = false; setBusy(false) }
    }
  }, [editor])

  const start = async (command: Pending) => {
    if (recoveryBlocked) throw new Error('本地保存恢复记录异常，当前数据表已禁止写入')
    if (pending.current || lock.current) throw new Error('已有保存请求尚未确认')
    if (!live.current.mounted || activeSession.current !== command.session) throw new Error('当前编辑会话已变化')
    if (!live.current.context || !sameScope(live.current.context.scope, command.scope)) throw new Error('当前数据范围与编辑会话不一致')
    writable()
    const snapshot = requireEditor()
    const storedEditor = command.kind === 'schemaSave' ? { ...snapshot, submittedSchema: clone(command.body.candidate) } : snapshot
    assertFiniteNumbers(command.body)
    localStorage.setItem(storageKey(command.scope), JSON.stringify({ pending: clone(command), editor: clone(storedEditor) }))
    if (command.kind === 'schemaSave') setEditor(clone(storedEditor))
    pending.current = clone(command); setRecoveryPending(false); setNotAccepted(false)
    return execute('submit')
  }
  const ready = (scope: Scope, session: string) => {
    if (recoveryBlocked) throw new Error('本地保存恢复记录异常，当前数据表已禁止写入')
    if (pending.current || lock.current) throw new Error('已有保存请求尚未确认')
    if (!live.current.mounted || activeSession.current !== session) throw new Error('当前编辑会话已变化')
    writable()
    if (!live.current.context || !sameScope(live.current.context.scope, scope)) throw new Error('当前数据范围与编辑会话不一致')
  }

  const open = (input: EditorInput) => {
    if (recoveryBlocked) throw new Error('本地保存恢复记录异常，当前数据表已禁止写入')
    if (!live.current.context) throw new Error('数据详情尚未载入')
    if (pending.current || lock.current || dialogBusy.current?.value || (editor && dirty.current)) throw new Error('当前编辑会话不能被覆盖')
    clearFlags(); setImpact(null); fieldImpact.current = null; schemaPreview.current = null; dirty.current = false
    const session = crypto.randomUUID(); epoch.current += 1; activeSession.current = session; dialogBusy.current = null; setDialogSaving(false)
    setEditor({ ...clone(live.current.context), ...clone(input), session } as DataEditor)
  }
  const close = () => { if (lock.current || pending.current || dialogBusy.current?.value) return false; epoch.current += 1; activeSession.current = null; dialogBusy.current = null; setDialogSaving(false); setEditor(null); setImpact(null); fieldImpact.current = null; schemaPreview.current = null; clearFlags(); dirty.current = false; return true }
  const replaceEditor = (context: EditingContext, input: EditorInput) => {
    if (lock.current || dialogBusy.current?.value || (pending.current && !notAccepted)) throw new Error('保存结果尚未确认')
    if (pending.current) clearStored(pending.current)
    pending.current = null; setRecoveryPending(false); setNotAccepted(false); setImpact(null); fieldImpact.current = null; schemaPreview.current = null; clearFlags(); dirty.current = false
    const session = crypto.randomUUID(); epoch.current += 1; activeSession.current = session; dialogBusy.current = null; setDialogSaving(false)
    setEditor({ ...clone(context), ...clone(input), session } as DataEditor)
  }

  const submitRecord = async (values: Schema['DataCellWrite'][]) => {
    const e = requireEditor()
    if (e.kind === 'recordCreate') { ready(e.scope, e.session); return start({ kind: e.kind, key: crypto.randomUUID(), scope: clone(e.scope), session: e.session, body: clone({ values }) }) }
    if (e.kind !== 'recordEdit') return Promise.reject(new Error('当前不是记录编辑会话'))
    if (!values.length) return Promise.reject(new Error('记录没有修改'))
    ready(e.scope, e.session); return start({ kind: e.kind, key: crypto.randomUUID(), scope: clone(e.scope), session: e.session, target: clone(e.record.ref.recordKey), body: clone({ values, expectedContentRevision: e.record.contentRevision }) })
  }
  const submitTable = async (values: { name: string; description: string }) => {
    const e = requireEditor(); if (e.kind !== 'tableEdit') return Promise.reject(new Error('当前不是数据表编辑会话'))
    const body: Schema['DataTablePatch'] = { expectedTableRevision: e.table.tableRevision }
    if (values.name !== e.table.name) body.name = values.name
    if (values.description !== e.table.description) body.description = values.description
    if (!('name' in body) && !('description' in body)) return Promise.reject(new Error('数据表没有修改'))
    ready(e.scope, e.session); return start({ kind: e.kind, key: crypto.randomUUID(), scope: clone(e.scope), session: e.session, body: clone(body) })
  }
  const submitRecordStatus = async (statusId: string | null) => {
    const e = requireEditor(); if (e.kind !== 'recordStatus') return Promise.reject(new Error('当前不是记录状态编辑会话'))
    if (statusId !== null && statusId === e.record.statusId) return Promise.reject(new Error('记录状态没有修改'))
    ready(e.scope, e.session); return start({ kind: e.kind, key: crypto.randomUUID(), scope: clone(e.scope), session: e.session, target: clone(e.record.ref.recordKey), body: { statusId, expectedStatusRevision: e.record.statusRevision, expectedFromStatusId: e.record.statusId } })
  }
  const submitField = async (submission: FieldSubmission) => {
    const e = requireEditor()
    if (e.kind === 'fieldCreate') { ready(e.scope, e.session); return start({ kind: e.kind, key: crypto.randomUUID(), scope: clone(e.scope), session: e.session, body: clone({ definition: submission.definition, expectedTableRevision: e.fields.tableRevision, sourceColumnPolicy: 'localOnly' as const, ...('existingRecordDefault' in submission ? { existingRecordDefault: submission.existingRecordDefault } : {}) }) }) }
    if (e.kind !== 'fieldEdit' || !('impactRevision' in submission)) return Promise.reject(new Error('字段修改尚未通过影响预检'))
    const report = fieldImpact.current
    if (!report || report.impactRevision !== submission.impactRevision || report.blockers.length || !validateImpact(e, report)) return Promise.reject(new Error('字段影响尚未通过预检'))
    ready(e.scope, e.session); return start({ kind: e.kind, key: crypto.randomUUID(), scope: clone(e.scope), session: e.session, target: e.field.ref.fieldId, body: clone({ definition: submission.definition, expectedFieldRevision: e.field.fieldRevision, expectedTableRevision: e.fields.tableRevision, impactRevision: submission.impactRevision }) })
  }
  const submitStatus = async (submission: StatusSubmission) => {
    const e = requireEditor()
    if (e.kind === 'statusCreate') { const parsed = statusFormSchema.parse(submission); ready(e.scope, e.session); return start({ kind: e.kind, key: crypto.randomUUID(), scope: clone(e.scope), session: e.session, body: { ...parsed, expectedTableRevision: e.statuses.tableRevision } }) }
    if (e.kind !== 'statusEdit') return Promise.reject(new Error('当前不是状态编辑会话'))
    if (!Object.keys(submission).length) return Promise.reject(new Error('状态没有修改'))
    ready(e.scope, e.session); return start({ kind: e.kind, key: crypto.randomUUID(), scope: clone(e.scope), session: e.session, target: e.status.statusId, body: clone({ ...submission, expectedStatusRevision: e.status.statusRevision, expectedTableRevision: e.statuses.tableRevision }) })
  }
  const submitSchema = async (body: Schema['DataSchemaCommit']) => {
    const e = requireEditor()
    if (e.kind !== 'schemaSave') return Promise.reject(new Error('当前不是架构保存会话'))
    const previewed = schemaPreview.current
    if (!previewed || previewed.impact.impactRevision !== body.impactRevision || previewed.impact.blockers.length || !sameValue(previewed.candidate, body.candidate)) return Promise.reject(new Error('架构影响尚未通过预检'))
    ready(e.scope, e.session)
    return start({ kind: e.kind, key: crypto.randomUUID(), scope: clone(e.scope), session: e.session, body: clone(body) })
  }

  const previewSchema = async (candidate: Schema['DataSchemaCandidate']) => {
    const e = requireEditor()
    if (e.kind !== 'schemaSave') throw new Error('当前不是架构保存会话')
    schemaPreview.current = null
    if (candidate.datasetGeneration !== e.scope.datasetGeneration || candidate.expectedTableRevision !== e.fields.tableRevision) throw new Error('资料已变化，请重新载入后编辑')
    ready(e.scope, e.session)
    lock.current = true; setBusy(true); setError(null)
    const run = epoch.current, usedClient = live.current.client, usedInstance = live.current.instanceId, session = e.session, runTicket = ++ticket.current
    try {
      const report = await createSchemaApi(usedClient, e.scope).preview(clone(candidate))
      if (runTicket !== ticket.current || !current(run, session, usedClient, usedInstance)) throw new Error('预检结果已过期')
      schemaPreview.current = { candidate: clone(candidate), impact: clone(report) }
      return report
    } catch (caught) {
      if (runTicket === ticket.current && run === epoch.current) { schemaPreview.current = null; setError(message(caught)) }
      throw caught
    } finally {
      if (runTicket === ticket.current && run === epoch.current) { lock.current = false; setBusy(false) }
    }
  }

  const validateImpact = (e: DataEditor, report: Impact) => {
    const revisions = report.expectedRevisions
    if (e.kind === 'fieldEdit') return report.target.type === 'field' && report.target.fieldRef.projectId === e.scope.projectId && report.target.fieldRef.tableId === e.scope.tableId && report.target.fieldRef.datasetGeneration === e.scope.datasetGeneration && report.target.fieldRef.fieldId === e.field.ref.fieldId && revisions.tableRevision === e.fields.tableRevision && revisions.fieldRevision === e.field.fieldRevision
    if (e.kind === 'recordDelete') return report.target.type === 'record' && report.target.recordRef.projectId === e.record.ref.projectId && report.target.recordRef.tableId === e.record.ref.tableId && report.target.recordRef.datasetGeneration === e.record.ref.datasetGeneration && report.target.recordRef.recordKey.type === e.record.ref.recordKey.type && report.target.recordRef.recordKey.value === e.record.ref.recordKey.value && revisions.tableRevision === e.fields.tableRevision && revisions.contentRevision === e.record.contentRevision && revisions.statusRevision === e.record.statusRevision && revisions.linkRevision === e.record.linkRevision
    if (e.kind === 'statusDelete') return report.target.type === 'status' && report.target.projectId === e.scope.projectId && report.target.tableId === e.scope.tableId && report.target.statusId === e.status.statusId && revisions.tableRevision === e.statuses.tableRevision && revisions.statusRevision === e.status.statusRevision
    return false
  }
  const preview = async (kind: 'field' | 'delete', definition?: Schema['DataFieldWrite']) => {
    const e = requireEditor(); if (lock.current) throw new Error('请求正在处理')
    if (pending.current) throw new Error('保存结果尚未确认')
    if (live.current.disabled || !live.current.context || !sameScope(live.current.context.scope, e.scope) || activeSession.current !== e.session) throw new Error('当前编辑上下文已变化')
    lock.current = true; setBusy(true); setError(null); const run = epoch.current, usedClient = live.current.client, usedInstance = live.current.instanceId, session = e.session, runTicket = ++ticket.current
    try {
      const catalog = createDataCatalogApi(usedClient, e.scope), records = createRecordsApi(usedClient, e.scope)
      const report = kind === 'field' && e.kind === 'fieldEdit' && definition ? await catalog.previewField(e.field.ref.fieldId, definition)
        : kind === 'delete' && e.kind === 'recordDelete' ? await records.previewDelete(e.record.ref.recordKey)
          : kind === 'delete' && e.kind === 'statusDelete' ? await catalog.previewStatusDelete(e.status.statusId) : null
      if (!report) throw new Error('当前编辑会话不支持该预检')
      if (runTicket !== ticket.current || !current(run, session, usedClient, usedInstance)) throw new Error('预检结果已过期')
      if (!validateImpact(e, report)) { if (kind === 'field') fieldImpact.current = null; else setImpact(null); throw new Error('资料已变化，请重新载入后编辑') }
      if (kind === 'field') fieldImpact.current = clone(report as Schema['FieldImpactReport'])
      else setImpact(clone(report as Schema['DeletionImpactReport']))
      return report
    } catch (caught) { if (runTicket === ticket.current && run === epoch.current) setError(message(caught)); throw caught }
    finally { if (runTicket === ticket.current && run === epoch.current) { lock.current = false; setBusy(false) } }
  }
  const previewField = (definition: Schema['DataFieldWrite']) => preview('field', definition) as Promise<Schema['FieldImpactReport']>
  const previewDelete = () => preview('delete') as Promise<Schema['DeletionImpactReport']>
  const confirmDelete = async () => {
    const e = requireEditor(), report = impact
    if (!report || report.blockers.length || !validateImpact(e, report)) return Promise.reject(new Error('删除影响尚未通过预检'))
    if (e.kind === 'recordDelete') { ready(e.scope, e.session); return start({ kind: e.kind, key: crypto.randomUUID(), scope: clone(e.scope), session: e.session, target: clone(e.record.ref.recordKey), body: { expectedContentRevision: e.record.contentRevision, expectedStatusRevision: e.record.statusRevision, expectedLinkRevision: e.record.linkRevision, impactRevision: report.impactRevision } }) }
    if (e.kind === 'statusDelete') { ready(e.scope, e.session); return start({ kind: e.kind, key: crypto.randomUUID(), scope: clone(e.scope), session: e.session, target: e.status.statusId, body: { expectedStatusRevision: e.status.statusRevision, expectedTableRevision: e.statuses.tableRevision, impactRevision: report.impactRevision } }) }
    return Promise.reject(new Error('当前不是删除会话'))
  }

  return {
    editor, error, busy: busy || dialogSaving, recoveryPending, recoveryBlocked, notAccepted, conflict, impact,
    open, close, submitTable, submitRecord, submitField, submitStatus, submitRecordStatus, submitSchema, previewSchema, previewDelete, confirmDelete, previewField,
    recover: () => execute('recover'), retryOriginal: () => { if (!notAccepted) return Promise.reject(new Error('原请求尚未确认未接受')); return execute('retry') },
    discardUnaccepted: () => { if (!notAccepted) return false; if (pending.current) clearStored(pending.current); pending.current = null; setNotAccepted(false); setRecoveryPending(false); setError(null); return true },
    replaceEditor,
    onDirtyChange: (value: boolean) => { dirty.current = value }, onSavingChange: ((session: string | undefined) => (value: boolean) => {
      if (!session || activeSession.current !== session) return
      if (value) dialogBusy.current = { session, value: true }
      else if (dialogBusy.current?.session === session) dialogBusy.current = { session, value: false }
      setDialogSaving(dialogBusy.current?.value ?? false)
    })(editor?.session),
    canLeave: () => !lock.current && !pending.current && !dialogBusy.current?.value,
  }
}
