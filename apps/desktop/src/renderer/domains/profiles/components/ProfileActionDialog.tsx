import { useId, useRef, useState, type FormEvent } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import { notify } from '../../../shared/components/Toaster'
import { FormField } from '../../../shared/components/FormField'
import { Button } from '../../../shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '../../../shared/components/ui/dialog'
import { Input } from '../../../shared/components/ui/input'
import { useDuplicateProfile, useRemoveProfile } from '../hooks'

export type ProfileAction = { kind: 'delete' | 'duplicate'; id: string; name: string }

export type ProfileActionDialogProps = {
  action: ProfileAction
  onClose(deleted?: boolean): void
}

const errorMessage = (error: unknown) => error instanceof Error ? error.message : '操作失败，请重试'

export function ProfileActionDialog({ action, onClose }: ProfileActionDialogProps) {
  const duplicate = useDuplicateProfile()
  const remove = useRemoveProfile()
  const [name, setName] = useState('')
  const [nameError, setNameError] = useState('')
  const [operationError, setOperationError] = useState('')
  const lock = useRef(false)
  const formId = useId()
  const copying = action.kind === 'duplicate'
  const busy = duplicate.isPending || remove.isPending

  const close = () => { if (!lock.current) onClose() }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (lock.current) return
    const trimmed = name.trim()
    if (copying && (!trimmed || [...trimmed].length > 120)) {
      setNameError(trimmed ? '名称最多 120 个字符' : '请输入新配置名称')
      return
    }
    lock.current = true
    setNameError('')
    setOperationError('')
    try {
      if (copying) await duplicate.mutateAsync({ profileId: action.id, body: { name: trimmed } })
      else await remove.mutateAsync(action.id)
      notify({ title: copying ? '配置已复制' : '配置已删除', tone: 'success' })
      onClose(!copying)
    } catch (error) {
      if (copying && error instanceof ApiClientError && error.fields?.name) setNameError(error.fields.name)
      else setOperationError(errorMessage(error))
    } finally {
      lock.current = false
    }
  }

  return <Dialog open onOpenChange={(open) => { if (!open) close() }} busy={busy}>
    <DialogContent className="w-[min(92vw,30rem)]">
      <DialogTitle>{copying ? '复制浏览器配置' : '删除浏览器配置'}</DialogTitle>
      <DialogDescription>{copying ? `复制自「${action.name}」` : `确认删除「${action.name}」？`}</DialogDescription>
      <form id={formId} className="grid gap-4" onSubmit={(event) => void submit(event)}>
        {copying ? <FormField label="新配置名称" htmlFor="profile-copy-name" error={nameError}>
          <Input autoFocus disabled={busy} value={name} placeholder="输入新配置名称" onChange={(event) => {
            setName(event.target.value)
            setNameError('')
            setOperationError('')
          }} />
        </FormField> : <p className="m-0 text-sm text-ink">配置及其浏览器数据将被删除，此操作不可撤销。</p>}
        {operationError ? <p role="alert" className="m-0 rounded-control border border-red-200 bg-red-50 p-3 text-sm text-red-800">{operationError}</p> : null}
      </form>
      <div className="flex justify-end gap-2">
        <Button type="button" autoFocus={!copying} disabled={busy} onClick={close}>取消</Button>
        <Button type="submit" form={formId} variant={copying ? 'primary' : 'danger'} disabled={busy}>
          {busy ? copying ? '正在复制…' : '正在删除…' : copying ? '创建副本' : '确认删除'}
        </Button>
      </div>
    </DialogContent>
  </Dialog>
}
