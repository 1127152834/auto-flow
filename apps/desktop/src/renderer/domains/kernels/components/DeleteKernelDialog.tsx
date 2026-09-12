import { useEffect } from 'react'
import type { KernelRef } from '../../../shared/api/types'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'

export type DeleteKernelDialogProps = {
  kernel: KernelRef | null
  busy: boolean
  disabled?: boolean
  error?: string | null
  onReconnect?(): void
  returnFocusTo?: HTMLButtonElement | null
  onOpenChange(open: boolean): void
  onConfirm(kernel: KernelRef): void | Promise<void>
}

export function DeleteKernelDialog({ kernel, busy, disabled = false, error, onReconnect, returnFocusTo, onOpenChange, onConfirm }: DeleteKernelDialogProps) {
  useEffect(() => {
    if (!kernel && returnFocusTo) window.requestAnimationFrame(() => returnFocusTo.focus())
  }, [kernel, returnFocusTo])

  return <AlertDialog open={Boolean(kernel)} onOpenChange={(open) => { if (!busy) onOpenChange(open) }}>
    <AlertDialogContent onEscapeKeyDown={(event) => { if (busy) event.preventDefault() }}>
      <AlertDialogTitle>删除浏览器内核</AlertDialogTitle>
      <AlertDialogDescription>将删除本机 CloakBrowser {kernel?.version} 文件，操作不可恢复。请先确认没有浏览器配置仍在使用这个内核。</AlertDialogDescription>
      {disabled ? <div role="alert" className="flex flex-col gap-3 rounded-control border border-warning/30 bg-warning-soft p-3 text-sm text-warning sm:flex-row sm:items-center sm:justify-between"><span>本地服务离线，内核尚未删除。</span>{onReconnect ? <Button type="button" onClick={onReconnect}>重新连接</Button> : null}</div> : null}
      {error ? <p role="alert" className="m-0 text-sm text-danger">{error}</p> : null}
      <div className="flex justify-end gap-2">
        <AlertDialogCancel asChild><Button type="button" autoFocus disabled={busy}>取消</Button></AlertDialogCancel>
        <AlertDialogAction asChild><Button type="button" variant="danger" disabled={disabled || busy} onClick={(event) => { event.preventDefault(); if (!disabled && kernel) void onConfirm(kernel) }}>{busy ? '正在删除…' : '确认删除'}</Button></AlertDialogAction>
      </div>
    </AlertDialogContent>
  </AlertDialog>
}
