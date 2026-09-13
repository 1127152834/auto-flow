import { useCallback, useEffect, useRef, useState } from 'react'
import { ConfirmDialog } from '../components/controls/confirm-dialog'
import { useWorkflowStore } from '../editor-store'
import { snapshotKey } from '../lib/snapshotKey'
import { useDialogRegistry } from './stores/dialogRegistry'

type Choice = 'save' | 'discard' | 'cancel'

/** One decision releases at most one pending document replacement. */
export function useDraftProtection(save: () => Promise<boolean>) {
  const [open, setOpen] = useState(false)
  const pending = useRef<((choice: Choice) => void) | null>(null)
  const busy = useRef(false)
  const mounted = useRef(true)
  const choose = useCallback((choice: Choice) => {
    pending.current?.(choice)
    pending.current = null
    setOpen(false)
  }, [])
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; pending.current?.('cancel'); pending.current = null }
  }, [])
  useEffect(() => {
    if (!open) return
    const id = `draft-leave-${crypto.randomUUID()}`
    const registry = useDialogRegistry.getState()
    registry.register({ id, type: 'draft_leave', title: '保存当前工作流？', actions: [
      { name: 'save', label: '保存后继续', primary: true, handler: () => choose('save') },
      { name: 'discard', label: '放弃修改', destructive: true, handler: () => choose('discard') },
      { name: 'cancel', label: '取消', handler: () => choose('cancel') },
    ] })
    return () => registry.unregister(id)
  }, [open, choose])

  const confirmLeave = useCallback(async () => {
    if (busy.current || !mounted.current) return false
    const state = useWorkflowStore.getState()
    if (!state.hasUnsavedChanges) return true
    busy.current = true
    const original = snapshotKey(state.exportWorkflow())
    try {
      const choice = await new Promise<Choice>(resolve => { pending.current = resolve; setOpen(true) })
      if (choice === 'cancel' || !mounted.current) return false
      if (snapshotKey(useWorkflowStore.getState().exportWorkflow()) !== original) {
        useWorkflowStore.getState().addLog({ level: 'warning', message: '确认期间草稿已修改，请重新操作' })
        return false
      }
      if (choice === 'save' && !(await save())) return false
      if (!mounted.current) return false
      const current = useWorkflowStore.getState()
      if (snapshotKey(current.exportWorkflow()) !== original || (choice === 'save' && current.hasUnsavedChanges)) {
        current.addLog({ level: 'warning', message: '保存期间草稿已修改，已保留当前编辑内容' })
        return false
      }
      return true
    } catch (error) {
      useWorkflowStore.getState().addLog({ level: 'error', message: `无法完成保存保护: ${String(error)}` })
      return false
    } finally { busy.current = false }
  }, [save])

  return {
    confirmLeave,
    draftDialog: <ConfirmDialog isOpen={open} title="保存当前工作流？"
      message="当前工作流有未保存的修改，请选择如何处理。" confirmText="保存后继续"
      secondaryText="放弃修改" onConfirm={() => choose('save')}
      onSecondary={() => choose('discard')} onCancel={() => choose('cancel')} />,
  }
}
