import { getStudioTransportRevision } from '../api/transport'
import { getDocumentLeaveResources, registerDocumentLeaveHandler, type LeaveOptions } from '../lib/documentLeave'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ConfirmDialog } from '../components/controls/confirm-dialog'
import { useWorkflowStore } from '../editor-store'
import { snapshotKey } from '../lib/snapshotKey'
import { useDialogRegistry } from './stores/dialogRegistry'

type Choice = 'save' | 'discard' | 'cancel'

/** One decision releases at most one pending document replacement. */
export function useDraftProtection(save: () => Promise<boolean>) {
  const [open, setOpen] = useState(false)
  const [dialog, setDialog] = useState({ title: '保存当前工作流？', message: '当前工作流有未保存的修改，请选择如何处理。', confirmText: '保存后继续', secondaryText: '放弃修改' })
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
    registry.register({ id, type: 'draft_leave', title: dialog.title, message: dialog.message, actions: [
      { name: 'save', label: dialog.confirmText, primary: true, handler: () => choose('save') },
      ...(dialog.secondaryText ? [{ name: 'discard', label: dialog.secondaryText, destructive: true, handler: () => choose('discard') }] : []),
      { name: 'cancel', label: '取消', handler: () => choose('cancel') },
    ] })
    return () => registry.unregister(id)
  }, [open, choose, dialog])

  const confirmLeave = useCallback(async (options?: LeaveOptions) => {
    if (sessionStorage.getItem('editingCustomModuleId') && !options?.preserveMainDocument) {
      useWorkflowStore.getState().addLog({ level: 'warning', message: '请先退出模块编辑并恢复主工作流，再新建或打开其他工作流' })
      return false
    }
    if (busy.current || !mounted.current) return false
    const state = useWorkflowStore.getState()
    const captured = getDocumentLeaveResources()
    if (!state.hasUnsavedChanges && !captured.length) return true
    const resourcesUnchanged = () => getDocumentLeaveResources().every(resource => captured.some(original => original.id === resource.id))
    const dirty = state.hasUnsavedChanges
    setDialog(captured.length ? {
      title: '结束活跃会话后离开？',
      message: `${captured.map(resource => resource.label).join('、')}仍活跃。${dirty ? '先处理未保存修改，再结束会话。' : '确认结束会话后继续。'}清理失败时保留当前流程。录制步骤保留在原流程的审查面板中。`,
      confirmText: dirty ? '保存并结束会话' : '结束会话后继续',
      secondaryText: dirty ? '放弃修改并结束会话' : '',
    } : { title: '保存当前工作流？', message: '当前工作流有未保存的修改，请选择如何处理。', confirmText: '保存后继续', secondaryText: '放弃修改' })
    busy.current = true
    const revision = getStudioTransportRevision()
    const original = snapshotKey(state.exportWorkflow())
    try {
      const choice = await new Promise<Choice>(resolve => { pending.current = resolve; setOpen(true) })
      if (choice === 'cancel' || !mounted.current) return false
      if (revision !== getStudioTransportRevision()) {
        useWorkflowStore.getState().addLog({ level: 'warning', message: '服务连接已变更，请重新确认离开；当前草稿已保留' })
        return false
      }
      if (snapshotKey(useWorkflowStore.getState().exportWorkflow()) !== original) {
        useWorkflowStore.getState().addLog({ level: 'warning', message: '确认期间草稿已修改，请重新操作' })
        return false
      }
      if (!resourcesUnchanged()) throw new Error('活跃会话已变更，请重新确认离开')
      if (choice === 'save' && dirty && !(await save())) return false
      if (!mounted.current || revision !== getStudioTransportRevision()) return false
      const current = useWorkflowStore.getState()
      if (snapshotKey(current.exportWorkflow()) !== original || (choice === 'save' && dirty && current.hasUnsavedChanges)) {
        current.addLog({ level: 'warning', message: '保存期间草稿已修改，已保留当前编辑内容' })
        return false
      }
      const stillSafe = () => mounted.current && revision === getStudioTransportRevision()
        && snapshotKey(useWorkflowStore.getState().exportWorkflow()) === original && resourcesUnchanged()
      for (const resource of captured) {
        if (!stillSafe()) throw new Error('草稿或活跃会话已变更，请重新确认离开')
        // A session may have finished naturally while the save dialog was open.
        if (!getDocumentLeaveResources().some(active => active.id === resource.id)) continue
        if (!(await resource.release())) throw new Error(`${resource.label}尚未确认结束，当前流程已保留`)
      }
      if (!stillSafe() || getDocumentLeaveResources().length) throw new Error('清理期间草稿或会话已变更，当前流程已保留')
      return true
    } catch (error) {
      useWorkflowStore.getState().addLog({ level: 'error', message: `无法完成保存保护: ${String(error)}` })
      return false
    } finally { busy.current = false }
  }, [save])

  useEffect(() => registerDocumentLeaveHandler(confirmLeave), [confirmLeave])

  return {
    confirmLeave,
    draftDialog: <ConfirmDialog isOpen={open} title={dialog.title}
      message={dialog.message} confirmText={dialog.confirmText}
      secondaryText={dialog.secondaryText} onConfirm={() => choose('save')}
      onSecondary={dialog.secondaryText ? () => choose('discard') : undefined} onCancel={() => choose('cancel')} />,
  }
}
