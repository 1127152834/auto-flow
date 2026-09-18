import { useEffect, useState } from 'react'
import { X } from '@phosphor-icons/react'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '../../../shared/components/ui/dialog'
import { Input } from '../../../shared/components/ui/input'

export type EnvironmentRenameDraft = { name: string; notes: string }
export type EnvironmentRenameDrawerProps = {
  open: boolean
  initialName: string
  initialNotes: string
  saving: boolean
  disabled?: boolean
  error?: string
  onOpenChange(open: boolean): void
  onSubmit(draft: EnvironmentRenameDraft): void
}

// The artboard keeps the rename in a right-hand panel so the environment's facts stay
// visible while the operator edits. Only the display name and notes are editable: the
// environment identity, its content generations and every task reference are untouched.
const nameProblem = (value: string): string | undefined => {
  const trimmed = value.trim()
  if (!trimmed) return '名称需 1–36 个字符'
  if ([...trimmed].length > 36) return '名称最多 36 个字符'
  return undefined
}

export function EnvironmentRenameDrawer({ open, initialName, initialNotes, saving, disabled, error, onOpenChange, onSubmit }: EnvironmentRenameDrawerProps) {
  const [name, setName] = useState(initialName)
  const [notes, setNotes] = useState(initialNotes)
  const [leave, setLeave] = useState(false)
  useEffect(() => {
    if (!open) return
    setName(initialName)
    setNotes(initialNotes)
    setLeave(false)
  }, [open, initialName, initialNotes])
  const dirty = name !== initialName || notes !== initialNotes
  const problem = nameProblem(name)
  const requestClose = () => { if (dirty) setLeave(true); else onOpenChange(false) }
  return <>
    <Dialog open={open} onOpenChange={value => { if (value) onOpenChange(true); else requestClose() }} busy={saving}>
      <DialogContent className="left-auto right-0 top-0 h-dvh w-[min(100vw,28rem)] max-w-none translate-x-0 translate-y-0 content-start overflow-y-auto rounded-none border-y-0 border-r-0 p-0 motion-safe:data-[state=open]:animate-in motion-safe:data-[state=open]:slide-in-from-right-2" aria-describedby="environment-rename-description">
        <header className="sticky top-0 z-10 flex items-start justify-between border-b border-line bg-surface/95 px-6 py-5 backdrop-blur">
          <div className="min-w-0">
            <DialogTitle>重命名环境</DialogTitle>
            <DialogDescription id="environment-rename-description" className="mt-1">只改显示名称，不改环境身份。</DialogDescription>
          </div>
          <Button className="h-9 w-9 shrink-0 px-0" variant="ghost" aria-label="关闭重命名" onClick={requestClose} disabled={saving}><X size={18} /></Button>
        </header>
        <form className="grid gap-4 p-6" aria-label="重命名环境" onSubmit={event => { event.preventDefault(); if (problem || saving || disabled) return; onSubmit({ name: name.trim(), notes }) }}>
          <label className="grid gap-1 text-sm" htmlFor="environment-rename-name"><span>当前名称</span></label>
          <Input id="environment-rename-name" aria-label="环境名称" value={name} maxLength={36} disabled={disabled} onChange={event => setName(event.target.value)} aria-invalid={problem ? true : undefined} aria-describedby={problem ? 'environment-rename-name-error' : undefined} />
          {problem
            ? <p id="environment-rename-name-error" role="alert" className="m-0 text-sm text-warning">{problem}</p>
            : <p className="m-0 text-sm text-muted">名称需 1–36 个字符；环境 ID 与任务引用不会改变，相关记录仍保持关联。</p>}
          <label className="grid gap-1 text-sm" htmlFor="environment-rename-notes"><span>备注（可选）</span></label>
          <Input id="environment-rename-notes" aria-label="环境备注" value={notes} maxLength={120} disabled={disabled} onChange={event => setNotes(event.target.value)} />
          {error ? <p role="alert" className="m-0 text-sm text-warning">{error}</p> : null}
          <div className="flex justify-end gap-2 border-t border-line pt-4">
            <Button type="button" variant="secondary" onClick={requestClose} disabled={saving}>取消</Button>
            <Button type="submit" disabled={disabled || saving || Boolean(problem)}>{saving ? '保存中…' : '保存名称'}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
    <AlertDialog open={leave} onOpenChange={value => { if (!value) setLeave(false) }}>
      <AlertDialogContent>
        <AlertDialogTitle>放弃未保存的名称修改？</AlertDialogTitle>
        <AlertDialogDescription>抽屉里还没有提交的修改会丢失；已保存的环境事实不受影响。</AlertDialogDescription>
        <div className="flex justify-end gap-2">
          <AlertDialogCancel asChild><Button>继续编辑</Button></AlertDialogCancel>
          <AlertDialogAction asChild><Button variant="primary" onClick={() => { setLeave(false); onOpenChange(false) }}>放弃修改</Button></AlertDialogAction>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  </>
}
