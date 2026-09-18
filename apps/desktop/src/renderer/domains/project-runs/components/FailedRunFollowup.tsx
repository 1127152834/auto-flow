import { useMemo, useState } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { notify } from '../../../shared/components/Toaster'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../../shared/components/ui/alert-dialog'
import { Button } from '../../../shared/components/ui/button'
import { DataCommandNotAccepted, DataCommandUncertain } from '../../project-data/data-command'
import { createProjectRunsApi, type FollowUpBatchRequest } from '../api'
import { presentRunFailure } from '../presentation'

export type FailedRunFollowupProps = {
  client: StreamingApiClient
  workspaceKey: string
  instanceId: string
  projectId: string
  taskId: string
  statusRevision: number
  disabled: boolean
  onOpenBatch(batchId: string): void
}

export function FailedRunFollowup({ client, workspaceKey, instanceId, projectId, taskId, statusRevision, disabled, onOpenBatch }: FailedRunFollowupProps) {
  const api = useMemo(() => createProjectRunsApi(client, projectId), [client, projectId])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [key, setKey] = useState<string | null>(null)
  const [error, setError] = useState<string>()
  const uncertain = Boolean(key)
  const submit = async (value: string, lookupOnly: boolean) => {
    const body: FollowUpBatchRequest = { mode: 'originalInputGroup', expectedTaskStatusRevision: statusRevision }
    setBusy(true); setError(undefined)
    try {
      const outcome = await api.followUp(taskId, body, value, { lookupOnly, retryIfNotAccepted: !lookupOnly })
      const batchId = outcome.state === 'succeeded' ? outcome.batch.batchId : (outcome.operation.resource as { batchId?: unknown }).batchId
      if (typeof batchId !== 'string') throw new DataCommandUncertain(new Error('accepted operation has no batch'))
      setOpen(false); setKey(null)
      notify({ title: '后续批次已创建', tone: 'success', operationId: JSON.stringify([workspaceKey, instanceId, value]) })
      onOpenBatch(batchId)
    } catch (failure) {
      if (failure instanceof DataCommandUncertain || failure instanceof DataCommandNotAccepted) {
        setKey(value)
        setError(failure instanceof DataCommandNotAccepted ? '原操作尚未被接受，可核对后再试。' : '结果尚未确认，请按原操作身份核对。')
      } else {
        setError(presentRunFailure(failure, '后续批次创建失败'))
      }
    } finally { setBusy(false) }
  }
  return <>
    <Button variant="secondary" disabled={disabled} onClick={() => setOpen(true)}>以此输入重新运行</Button>
    <AlertDialog open={open} onOpenChange={value => { if (!busy) setOpen(value) }}>
      <AlertDialogContent onEscapeKeyDown={event => { if (busy) event.preventDefault() }}>
        <AlertDialogTitle>从原输入组重新运行？</AlertDialogTitle>
        <AlertDialogDescription>会新建一个只包含本次任务原输入组的批次，按当前业务状态和条件重新核对候选；已经发生的网页动作不会重放，本次失败记录保持不变。原输入为空的可选输入保持为空。</AlertDialogDescription>
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        <div className="flex justify-end gap-2">
          <AlertDialogCancel asChild><Button disabled={busy}>取消</Button></AlertDialogCancel>
          {uncertain && key
            ? <Button variant="secondary" loading={busy} disabled={busy || disabled} onClick={() => void submit(key, true)}>核对原操作</Button>
            : <Button loading={busy} disabled={busy || disabled} onClick={() => { const value = crypto.randomUUID(); setKey(value); void submit(value, false) }}>确认重新运行</Button>}
        </div>
      </AlertDialogContent>
    </AlertDialog>
  </>
}
