import { useCallback, useEffect, useRef, useState } from 'react'
import { useDialogRegistry } from './stores/dialogRegistry'
import { ConfirmDialog } from '../components/controls/confirm-dialog'
export type SettingsLeaveGuard = () => Promise<boolean>
export type RegisterSettingsLeaveGuard = (guard: SettingsLeaveGuard | null) => void

/** Protect the active settings form before its parent changes tabs or closes. */
export function useSettingsDraftProtection(
  register: RegisterSettingsLeaveGuard | undefined,
  title: string,
  dirty: boolean,
  busy: boolean,
  save: () => Promise<boolean>,
) {
  const [open, setOpen] = useState(false)
  const [pending, setPending] = useState(false)
  const deciding = useRef(false)
  const mounted = useRef(true)
  const resolve = useRef<((choice: 'save' | 'discard' | 'cancel') => void) | null>(null)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; resolve.current?.('cancel'); resolve.current = null }
  }, [])
  useEffect(() => {
    if (!register) return
    register(async () => {
      if (busy || deciding.current || !mounted.current) return false
      if (!dirty) return true
      deciding.current = true
      setPending(true)
      try {
        const choice = await new Promise<'save' | 'discard' | 'cancel'>(done => { resolve.current = done; setOpen(true) })
        if (!mounted.current || choice === 'cancel') return false
        if (choice === 'discard') return true
        return await save() && mounted.current
      } finally {
        deciding.current = false
        if (mounted.current) setPending(false)
      }
    })
    return () => register(null)
  }, [register, title, dirty, busy, save])
  const choose = useCallback((choice: 'save' | 'discard' | 'cancel') => {
    resolve.current?.(choice)
    resolve.current = null
    setOpen(false)
  }, [])
  useEffect(() => {
    if (!open) return
    const id = `settings-leave-${crypto.randomUUID()}`
    const registry = useDialogRegistry.getState()
    registry.register({ id, type: 'settings_leave', title, actions: [
      { name: 'save', label: '保存后继续', primary: true, handler: () => choose('save') },
      { name: 'discard', label: '放弃修改', destructive: true, handler: () => choose('discard') },
      { name: 'cancel', label: '取消', handler: () => choose('cancel') },
    ] })
    return () => registry.unregister(id)
  }, [open, title, choose])
  return { pending, dialog: <ConfirmDialog isOpen={open} title={title}
    message="当前配置有未提交的修改，请选择如何处理。" confirmText="保存后继续" secondaryText="放弃修改"
    onConfirm={() => choose('save')} onSecondary={() => choose('discard')} onCancel={() => choose('cancel')} /> }
}
