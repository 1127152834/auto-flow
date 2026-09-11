import { useEffect } from 'react'
import type { KernelRef } from '../../../shared/api/types'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'

export type DeleteKernelDialogProps = {
  kernel: KernelRef | null
  busy: boolean
  error?: string | null
  returnFocusTo?: HTMLButtonElement | null
  onOpenChange(open: boolean): void
  onConfirm(kernel: KernelRef): void | Promise<void>
}

export function DeleteKernelDialog({ kernel, busy, error, returnFocusTo, onOpenChange, onConfirm }: DeleteKernelDialogProps) {
  useEffect(() => {
    if (!kernel && returnFocusTo) window.requestAnimationFrame(() => returnFocusTo.focus())
  }, [kernel, returnFocusTo])

  return <AlertDialog open={Boolean(kernel)} onOpenChange={(open) => { if (!busy) onOpenChange(open) }}>
    <AlertDialogContent onEscapeKeyDown={(event) => { if (busy) event.preventDefault() }}>
      <AlertDialogTitle>删除浏览器内核</AlertDialogTitle>
      <AlertDialogDescription>将删除本机 CloakBrowser {kernel?.version} 文件，操作不可恢复。请先确认没有浏览器配置仍在使用这个内核。</AlertDialogDescription>
      {error ? <p role="alert" className="m-0 text-sm text-red-700">{error}</p> : null}
      <div className="flex justify-end gap-2">
        <AlertDialogCancel asChild><Button type="button" autoFocus disabled={busy}>取消</Button></AlertDialogCancel>
        <AlertDialogAction asChild><Button type="button" variant="danger" disabled={busy} onClick={(event) => { event.preventDefault(); if (kernel) void onConfirm(kernel) }}>{busy ? '正在删除…' : '确认删除'}</Button></AlertDialogAction>
      </div>
    </AlertDialogContent>
  </AlertDialog>
}
