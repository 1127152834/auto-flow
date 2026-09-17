import { useEffect, useRef, useState } from 'react'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import { createRecordsApi } from './records-api'
import { DataCommandNotAccepted } from './data-command'
import { addDraftRow, draftHistory, gridValues, hasDraftValues, removeDraftRow, undoDraft, updateDraftCell, type DraftHistory, type GridCell, type GridError, type GridField } from './record-grid-draft'
import { pasteGridCells } from './record-grid-clipboard'
import { readGridSession, writeGridSession, type GridPending, type GridScope, type GridSession } from './record-grid-storage'
import type { GridSaveState } from './components/RecordDraftSaveBar'

type Options = { scope: GridScope; instanceKey: string; fields: GridField[]; tableRevision: number; writable: boolean; busy?: boolean
  client: StreamingApiClient; storage: Pick<Storage, 'getItem' | 'setItem'>; onSaved(count: number, operationKey: string): void }
const scopeKey = (scope: GridScope) => JSON.stringify([scope.workspaceId, scope.projectId, scope.tableId, scope.datasetGeneration])
const requestKey = (o: Options) => JSON.stringify([scopeKey(o.scope), o.instanceKey])
function load(o: Options) {
  const empty: GridSession = { schemaVersion: 1, scope: o.scope, tableRevision: o.tableRevision, rows: [], pending: null, receipt: null }
  try { return { session: readGridSession(o.storage, o.scope, true) ?? empty, error: '' } }
  catch { return { session: empty, error: '草稿读取失败，请重试' } }
}
export function useRecordGridEntry(options: Options) {
  const [initial] = useState(() => load(options))
  const session = useRef(initial.session), history = useRef(draftHistory(initial.session.rows))
  const current = useRef(options); current.current = options
  const mounted = useRef(true), working = useRef(false), blocked = useRef(Boolean(initial.error))
  const [rows, setRows] = useState(initial.session.rows)
  const [state, setState] = useState<GridSaveState>(initial.error ? 'stale' : initial.session.pending ? 'uncertain' : initial.session.scope.datasetGeneration !== options.scope.datasetGeneration ? 'stale' : 'draft')
  const [message, setMessage] = useState(initial.error)
  const [errors, setErrors] = useState<GridError[]>([])
  const [focusCell, setFocusCell] = useState<{ rowId: string; fieldId: string; sequence: number }>()
  const focusSequence = useRef(0)
  const token = requestKey(options)
  const epoch = useRef({ token, value: 0 })
  if (epoch.current.token !== token) epoch.current = { token, value: epoch.current.value + 1 }
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    const next = load(current.current)
    session.current = next.session; history.current = draftHistory(next.session.rows); blocked.current = Boolean(next.error)
    working.current = false; setRows(next.session.rows); setErrors([]); setMessage(next.error)
    if (next.session.scope.datasetGeneration !== current.current.scope.datasetGeneration) setMessage('数据已更新，旧草稿已保留；请核验原保存结果，或复制输入后放弃旧草稿再继续')
    setState(next.error ? 'stale' : next.session.pending ? 'uncertain' : next.session.scope.datasetGeneration !== current.current.scope.datasetGeneration ? 'stale' : 'draft')
  }, [token])
  useEffect(() => {
    if (blocked.current || session.current.pending || scopeKey(session.current.scope) !== scopeKey(current.current.scope)) return
    if (!hasDraftValues(session.current.rows)) {
      session.current = { ...session.current, tableRevision: current.current.tableRevision }
    } else if (session.current.tableRevision !== current.current.tableRevision) {
      setState('stale'); setMessage('字段已更新，你的输入已保留，请确认最新字段后继续')
    }
  }, [options.tableRevision, token])
  const alive = (origin: string, sequence: number) => mounted.current && requestKey(current.current) === origin && epoch.current.value === sequence
  const editable = () => !working.current && !blocked.current && !session.current.pending && current.current.writable && !current.current.busy
    && scopeKey(session.current.scope) === scopeKey(current.current.scope) && session.current.tableRevision === current.current.tableRevision
  const focus = (rowId: string, fieldId: string) => setFocusCell({ rowId, fieldId, sequence: ++focusSequence.current })
  const persist = (next: GridSession) => { writeGridSession(current.current.storage, next); session.current = next }
  const change = (next: DraftHistory) => {
    history.current = next; session.current = { ...session.current, rows: next.rows }; setRows(next.rows); setErrors([])
    try { persist(session.current); setMessage('') } catch { setMessage('草稿尚未保存，请重试') }
  }
  const addRow = (focusFieldId?: string) => {
    if (!editable()) return
    try {
      const next = addDraftRow(history.current, current.current.fields)
      change(next)
      const field = current.current.fields.find(f => f.ref.fieldId === focusFieldId && f.writable && !f.formula) ?? current.current.fields.find(f => f.writable && !f.formula)
      if (field) focus(next.rows[next.rows.length - 1].clientRowId, field.ref.fieldId)
    } catch { setMessage('无法新增记录，请重试') }
  }
  const run = async (pending: GridPending, lookupOnly: boolean) => {
    if (working.current) return
    const origin = requestKey(current.current), sequence = epoch.current.value, started = current.current, frozen = session.current
    working.current = true; setState(lookupOnly ? 'recovering' : 'submitting'); setMessage('')
    const canSubmit = () => alive(origin, sequence) && current.current.writable && !current.current.busy
      && current.current.tableRevision === pending.payload.expectedTableRevision
    try {
      const api = createRecordsApi(started.client, frozen.scope)
      const result = await api.createBatch(pending.payload, pending.key, lookupOnly, { lookupOnly, canSubmit })
      if (!alive(origin, sequence)) return
      const receipt = { key: pending.key, clientRowIds: result.records.map(r => r.clientRowId) }
      // Keep a durable receipt before clearing: interruption between the two writes remains recoverable.
      persist({ ...frozen, pending, receipt })
      const remaining = frozen.rows.filter(r => !receipt.clientRowIds.includes(r.clientRowId))
      const meaningful = remaining.filter(r => hasDraftValues([r]))
      const oldGeneration = frozen.scope.datasetGeneration !== current.current.scope.datasetGeneration
      persist({ ...frozen, ...(oldGeneration ? {scope: current.current.scope, tableRevision: current.current.tableRevision} : {}), rows: oldGeneration ? [] : meaningful, pending: null, receipt: null })
      history.current = draftHistory(oldGeneration ? [] : meaningful); setRows(oldGeneration ? [] : meaningful); setErrors([]); setState('draft')
      setMessage(`已新增 ${receipt.clientRowIds.length} 条记录`)
      try { if (oldGeneration) setMessage('原数据中的保存已确认，当前数据没有重复新增'); else started.onSaved(receipt.clientRowIds.length, pending.key) }
      catch { setMessage(`已新增 ${receipt.clientRowIds.length} 条记录，列表刷新失败，请重试读取`) }
    } catch (error) {
      if (!alive(origin, sequence)) return
      if (error instanceof DataCommandNotAccepted) {
        setState('notAccepted'); setMessage('已确认原操作尚未接受，可重发原请求')
      } else if (error instanceof ApiClientError && error.code === 'OPERATION_PAYLOAD_MISMATCH') {
        setState('uncertain'); setMessage('原操作身份与请求不一致，已保留恢复证据，请核验原操作，不能改用新身份重复保存')
      } else if (!lookupOnly && error instanceof ApiClientError && error.status >= 400 && error.status < 500 && error.status !== 408) {
        try { persist({ ...frozen, pending: null, receipt: null }) } catch { setState('uncertain'); setMessage('保存未通过，但恢复信息尚未更新，请先查询原操作'); return }
        const details = error.details.rowErrors
        const rowErrors: GridError[] = Array.isArray(details) ? details.flatMap(item => {
          if (!item || typeof item !== 'object' || typeof item.clientRowId !== 'string' || typeof item.message !== 'string') return []
          if (!frozen.rows.some(r => r.clientRowId === item.clientRowId)) return []
          return [{ clientRowId: item.clientRowId, fieldId: typeof item.fieldId === 'string' ? item.fieldId : null, message: item.code === 'RECORD_ALREADY_EXISTS' ? '记录身份已存在，请填写不同的身份值' : '记录未保存，请检查输入后重试' }]
        }) : []
        setErrors(rowErrors); setState(error.code === 'REVISION_CONFLICT' ? 'stale' : 'draft'); setMessage(error.code === 'RECORD_ALREADY_EXISTS' ? '本次新增未保存，请检查重复的记录身份' : error.code === 'REVISION_CONFLICT' ? '字段已更新，请确认最新字段后再保存' : '操作失败，请重试')
        if (rowErrors[0]?.fieldId) focus(rowErrors[0].clientRowId, rowErrors[0].fieldId)
      } else { setState('uncertain'); setMessage('保存结果尚未确认，请查询原操作；不会自动重复新增') }
    } finally { if (alive(origin, sequence)) working.current = false }
  }
  const save = async () => {
    if (working.current || blocked.current || !current.current.writable || current.current.busy) return
    if (session.current.pending) { if (state === 'notAccepted') await run(session.current.pending, false); return }
    if (!editable()) { setState('stale'); setMessage('数据结构已更新，请确认最新字段后再保存'); return }
    const checked = gridValues(current.current.fields, history.current.rows)
    setErrors(checked.errors)
    if (checked.errors.length) { const first = checked.errors[0]; if (first.fieldId) focus(first.clientRowId, first.fieldId); return }
    if (!checked.rows.length) return
    const pending: GridPending = { key: crypto.randomUUID(), payload: { datasetGeneration: session.current.scope.datasetGeneration, expectedTableRevision: session.current.tableRevision, rows: checked.rows } }
    try { persist({ ...session.current, pending, receipt: null }) } catch { setMessage('保存请求尚未发送，请重试'); return }
    await run(pending, false)
  }
  const reconcile = async () => { if (session.current.pending) await run(session.current.pending, true) }
  const discard = () => {
    if (working.current || (session.current.pending && state !== 'notAccepted') || blocked.current) return
    session.current = { ...session.current, scope: current.current.scope, tableRevision: current.current.tableRevision, pending: null, receipt: null }
    // The page owns the explicit unsaved-confirmation interaction before invoking discard.
    change(draftHistory()); setState('draft')
  }
  const adoptSchema = () => {
    if (working.current || session.current.pending || blocked.current) return
    if (session.current.scope.datasetGeneration !== current.current.scope.datasetGeneration) { setMessage('旧数据草稿不能写入新数据，请先核验原操作或放弃旧草稿'); return }
    const validIds = new Set(current.current.fields.map(f => f.ref.fieldId))
    if (session.current.rows.some(r => Object.entries(r.cells).some(([id,cell]) => !validIds.has(id) && cell.presence !== 'missing'))) {
      setMessage('旧字段中仍有输入，请先复制或放弃这些输入，不能自动删除'); return
    }
    session.current = { ...session.current, tableRevision: current.current.tableRevision }
    change(history.current); setState('draft')
  }
  return { rows, state, message, errors, focusCell, dirty: hasDraftValues(rows), pending: Boolean(session.current.pending), count: rows.filter(r => hasDraftValues([r])).length,
    editable: editable(), addRow, save, reconcile, discard, adoptSchema,
    changeCell: (id: string, fieldId: string, value: GridCell) => { if (editable()) change(updateDraftCell(history.current, id, fieldId, value)) },
    removeRow: (id: string) => { if (editable()) change(removeDraftRow(history.current, id)) },
    undo: () => { if (editable()) change(undoDraft(history.current)) },
    paste: (columns: GridField[], row: number, column: number, text: string) => {
      if (!editable()) return
      try { change(pasteGridCells(history.current, current.current.fields, columns, row, column, text)) } catch { setMessage('粘贴内容无法应用，请检查格式后重试') }
    },
  }
}
