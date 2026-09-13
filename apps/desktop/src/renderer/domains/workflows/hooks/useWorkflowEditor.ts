import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import type { WorkflowApi } from '../api'
import { createWorkflow, signature } from '../editor-model'
import { createHistory, editHistory, redoHistory, undoHistory, type WorkflowHistory } from '../history'
import type { WorkflowContent, WorkflowRead } from '../types'

export function useWorkflowEditor(api: WorkflowApi, writable: boolean) {
  const [history, setHistory] = useState<WorkflowHistory>(() => createHistory(createWorkflow()))
  const historyRef = useRef(history)
  const [saved, setSaved] = useState<WorkflowRead | null>(null)
  const savedRef = useRef<WorkflowRead | null>(null)
  const baseline = useRef(signature(history.present))
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const currentApi = useRef(api)
  currentApi.current = api
  const canWrite = useRef(writable)
  canWrite.current = writable
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  const group = useRef<{ changed: boolean } | null>(null)
  const pending = useRef<Promise<boolean> | null>(null)
  const epoch = useRef(0)
  const [documentSession, setDocumentSession] = useState(0)

  const update = useCallback((next: WorkflowHistory) => { historyRef.current = next; setHistory(next) }, [])
  const mutate = useCallback((transform: (content: WorkflowContent) => WorkflowContent) => {
    const previous = historyRef.current
    const content = transform(previous.present)
    const changed = signature(previous.present) !== signature(content)
    update(editHistory(previous, content, group.current?.changed))
    if (changed && group.current) group.current.changed = true
  }, [update])
  const beginEdit = useCallback(() => { group.current ??= { changed: false } }, [])
  const endEdit = useCallback(() => { group.current = null }, [])
  const undo = useCallback(() => { group.current = null; update(undoHistory(historyRef.current)) }, [update])
  const redo = useCallback(() => { group.current = null; update(redoHistory(historyRef.current)) }, [update])
  const replace = useCallback((record?: WorkflowRead) => {
    epoch.current += 1
    setDocumentSession(epoch.current)
    group.current = null
    const content = record ? { document: { ...record.document, schemaVersion: 2 as const }, layout: record.layout } : createWorkflow()
    baseline.current = signature(content)
    savedRef.current = record ?? null
    setSaved(record ?? null)
    setConflict(false)
    setMessage(null)
    update(createHistory(content))
  }, [update])

  const save = useCallback((): Promise<boolean> => {
    if (pending.current) return pending.current
    if (!canWrite.current) { setMessage('本地服务不可用或工作区正在切换，请恢复连接后保存'); return Promise.resolve(false) }
    const snapshot = structuredClone(historyRef.current.present)
    const revision = savedRef.current?.revision
    const operationEpoch = epoch.current
    setSaving(true)
    setMessage(null)
    const request = (async () => {
      try {
        const record = await (revision === undefined ? currentApi.current.create(snapshot) : currentApi.current.save(snapshot, revision))
        if (!alive.current || operationEpoch !== epoch.current) return false
        savedRef.current = record
        baseline.current = signature(record)
        setSaved(record)
        setConflict(false)
        return signature(historyRef.current.present) === baseline.current
      } catch (error) {
        if (!alive.current || operationEpoch !== epoch.current) return false
        setConflict(error instanceof ApiClientError && error.status === 409)
        setMessage(error instanceof Error ? error.message : '保存失败，当前编辑内容已保留')
        return false
      } finally {
        pending.current = null
        if (alive.current) setSaving(false)
      }
    })()
    pending.current = request
    return request
  }, [])

  const saveAsNew = useCallback(async () => {
    if (pending.current || !canWrite.current) return false
    const content = historyRef.current.present
    const next = { ...content, document: { ...content.document, id: crypto.randomUUID(), name: `${content.document.name} 副本` } }
    savedRef.current = null
    baseline.current = ''
    setSaved(null)
    setConflict(false)
    group.current = null
    update(createHistory(next))
    return save()
  }, [save, update])

  return {
    history, content: history.present, saved, saving, message, conflict, documentSession,
    dirty: signature(history.present) !== baseline.current,
    mutate, beginEdit, endEdit, undo, redo, replace, save, saveAsNew, setMessage,
    isDirty: () => signature(historyRef.current.present) !== baseline.current,
    current: () => historyRef.current.present,
    waitForSave: async () => { await pending.current },
  }
}
