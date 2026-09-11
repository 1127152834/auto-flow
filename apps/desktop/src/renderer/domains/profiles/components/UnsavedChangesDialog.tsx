import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'

export type UnsavedChangesDialogProps = {
  open: boolean
  onOpenChange(open: boolean): void
  onDiscard(): void
}

export function UnsavedChangesDialog({ open, onOpenChange, onDiscard }: UnsavedChangesDialogProps) {
  return <AlertDialog open={open} onOpenChange={onOpenChange}>
    <AlertDialogContent>
      <AlertDialogTitle>放弃未保存的修改？</AlertDialogTitle>
      <AlertDialogDescription>关闭后，本次对浏览器配置的修改将不会保存。</AlertDialogDescription>
      <div className="flex justify-end gap-2">
        <AlertDialogCancel asChild><Button autoFocus>继续编辑</Button></AlertDialogCancel>
        <AlertDialogAction asChild><Button variant="danger" onClick={onDiscard}>放弃修改</Button></AlertDialogAction>
      </div>
    </AlertDialogContent>
  </AlertDialog>
}
