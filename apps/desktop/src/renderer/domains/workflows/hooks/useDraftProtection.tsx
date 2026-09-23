import { getStudioTransportRevision } from '../api/transport'
import { getDocumentLeaveResources, registerDocumentLeaveHandler, type LeaveOptions } from '../lib/documentLeave'
import { useCallback, useEffect, useRef, useState } from 'react'
import { DialogPortal } from '../components/controls/dialog-portal'
import { ConfirmDialog } from '../components/controls/confirm-dialog'
import { useWorkflowStore } from '../editor-store'
import { snapshotKey } from '../lib/snapshotKey'
import { useDialogRegistry } from './stores/dialogRegistry'

type Choice = 'save' | 'discard' | 'cancel'

/** One decision releases at most one pending document replacement. */
export function useDraftProtection(save: () => Promise<boolean>) {
  const [open, setOpen] = useState(false)
  const [leaveError, setLeaveError] = useState('')
  const [dialog, setDialog] = useState({ title: '保存当前工作流？', message: '当前工作流有未保存的修改，请选择如何处理。', confirmText: '保存后继续', secondaryText: '放弃修改' })
  const pending = useRef<((choice: Choice) => void) | null>(null)
  const resolvedSessionPrompt = useRef<(() => boolean) | null>(null)
  const executionStatus = useWorkflowStore(state => state.executionStatus)
  const busy = useRef(false)
  const mounted = useRef(true)
  const choose = useCallback((choice: Choice) => {
    pending.current?.(choice)
    pending.current = null
    setOpen(false)
  }, [])
  useEffect(() => {
    // A completed run (including restored terminal events) no longer needs a stop decision.
    // Continue the original request only if it never needed a draft decision.
    if (open && resolvedSessionPrompt.current?.()) choose('save')
  }, [open, executionStatus, choose])
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
    const readResources=()=>getDocumentLeaveResources().filter(resource=>!options?.keepBrowser||resource.kind!=='browser')
    const captured = readResources()
    const dirty = !options?.sessionsOnly && state.hasUnsavedChanges
    if (!dirty && !captured.length) return true
    resolvedSessionPrompt.current = captured.length && !dirty
      ? () => !useWorkflowStore.getState().hasUnsavedChanges && readResources().length === 0
      : null
    const resourcesUnchanged = () => readResources().every(resource => captured.some(original => original.id === resource.id))
    setDialog(captured.length ? {
      title: '结束活跃会话后离开？',
      message: `${captured.map(resource => resource.label).join('、')}仍活跃。${dirty ? '先处理未保存修改，再结束会话。' : '确认结束会话后继续。'}清理失败时保留当前流程。录制步骤会保存到原流程的审查；审查保存失败时不会离开。`,
      confirmText: dirty ? '保存并结束会话' : '结束会话后继续',
      secondaryText: dirty ? '放弃修改并结束会话' : '',
    } : { title: '保存当前工作流？', message: '当前工作流有未保存的修改，请选择如何处理。', confirmText: '保存后继续', secondaryText: '放弃修改' })
    setLeaveError('')
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
      if (choice === 'save' && dirty && !(await save())) {
        if (mounted.current) setLeaveError('未完成保存，未离开。草稿和活跃会话已保留，请处理保存问题后重试。')
        return false
      }
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
        if (!readResources().some(active => active.id === resource.id)) continue
        if (!(await resource.release())) throw new Error(`${resource.label}尚未确认结束，当前流程已保留`)
      }
      if (!stillSafe() || readResources().length) throw new Error('清理期间草稿或会话已变更，当前流程已保留')
      return true
    } catch (error) {
      const message = `无法完成保存保护: ${String(error)}`
      useWorkflowStore.getState().addLog({ level: 'error', message })
      if (mounted.current) setLeaveError(message)
      return false
    } finally { busy.current = false; resolvedSessionPrompt.current = null }
  }, [save])

  useEffect(() => registerDocumentLeaveHandler(confirmLeave), [confirmLeave])

  return {
    confirmLeave,
    draftDialog: <><ConfirmDialog isOpen={open} title={dialog.title}
      message={dialog.message} confirmText={dialog.confirmText}
      secondaryText={dialog.secondaryText} onConfirm={() => choose('save')}
      onSecondary={dialog.secondaryText ? () => choose('discard') : undefined} onCancel={() => choose('cancel')} />
      {leaveError && <DialogPortal><div role="alert" className="fixed bottom-4 right-4 z-[1000] max-w-md rounded border border-red-300 bg-[hsl(var(--card))] p-3 text-sm shadow-lg">
        <p>{leaveError}</p><button type="button" onClick={() => setLeaveError('')}>关闭提示</button>
      </div></DialogPortal>}</>,
  }
}
