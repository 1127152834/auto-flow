import { NotePencil, WarningCircle, X } from '@phosphor-icons/react'
import { AlertDialog, AlertDialogContent, AlertDialogTitle, AlertDialogDescription, AlertDialogCancel, AlertDialogAction } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { IconButton } from '../../../shared/components/ui/icon-button'

export function RecordUnsavedDialog({ open, title, dirtyFields, invalidFields, onOpenChange, onDiscard }: {
  open: boolean; title: string; dirtyFields: string[]; invalidFields: string[]
  onOpenChange(open: boolean): void; onDiscard(): void
}) {
  return <AlertDialog open={open} onOpenChange={onOpenChange}>
    <AlertDialogContent className="w-[min(92vw,40rem)] gap-6 p-7">
      <AlertDialogCancel asChild><IconButton aria-label="关闭" variant="ghost" className="absolute right-3 top-3"><X size={20} /></IconButton></AlertDialogCancel>
      <div className="flex min-w-0 gap-7 pr-3">
        <span className="flex size-20 shrink-0 items-center justify-center rounded-card border border-clay/10 bg-clay/5 text-clay"><NotePencil size={36} /></span>
        <div className="min-w-0"><AlertDialogTitle className="mb-2 text-2xl">有未保存的修改</AlertDialogTitle>
          <AlertDialogDescription className="break-words text-base leading-7">你正在编辑「{title}」。<br />离开将丢弃本次草稿，已保存的数据不会改变。</AlertDialogDescription></div>
      </div>
      <div className="flex min-w-0 items-start gap-3 rounded-control border border-warning/20 bg-warning/5 p-4 text-warning">
        <WarningCircle size={24} weight="fill" className="shrink-0" /><div className="min-w-0 break-words text-base"><p className="m-0 font-semibold">{dirtyFields.length ? dirtyFields.join('、') : '当前记录草稿'}</p>
          {invalidFields.length ? <p className="mb-0 mt-2">{invalidFields.join('、')}尚未通过校验，请继续编辑后保存。</p> : null}</div>
      </div>
      <div className="flex flex-wrap justify-end gap-3">
        <AlertDialogAction asChild><Button className="h-12 min-w-40 text-base" onClick={onDiscard}>丢弃并离开</Button></AlertDialogAction>
        <AlertDialogCancel asChild><Button autoFocus variant="primary" className="h-12 min-w-40 text-base">继续编辑</Button></AlertDialogCancel>
      </div>
    </AlertDialogContent>
  </AlertDialog>
}
