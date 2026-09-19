import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { AiModel } from '../model'
import type { ModelApi } from '../api'
import { Modal } from '../../../shared/components/Modal'
import { ResourceReferenceList } from '../../../shared/components/ResourceReferenceList'
import { Button } from '../../../shared/components/ui/button'
import { refreshAfterModelConflict } from '../cache'

export function ModelDeleteDialog({ open, onOpenChange, model, api, onRemoved, instanceId, blocked = false }: { open: boolean; onOpenChange(open: boolean): void; model: AiModel; api: ModelApi; onRemoved(): void; instanceId: string; blocked?: boolean }) {
  const cache = useQueryClient()
  const remove = useMutation({ mutationFn: () => api.removeModel(model.id), retry: false, onSuccess: () => { onOpenChange(false); onRemoved() }, onError: (error) => refreshAfterModelConflict(cache, instanceId, error) })
  return <Modal open={open} onOpenChange={onOpenChange} closeDisabled={remove.isPending} size="small" title="删除模型" description={`确认从目录移除“${model.displayName}”？`} footer={<><Button type="button" disabled={remove.isPending} onClick={() => onOpenChange(false)}>取消</Button><Button type="button" variant="danger" disabled={remove.isPending || blocked} onClick={() => remove.mutate()}>{remove.isPending ? '正在移除…' : '确认移除'}</Button></>}>
    <p>只移除 AutoFlow 中的模型配置，不会删除供应商的远端模型。</p>{remove.error ? <p role="alert" className="mt-3 text-sm text-clay">{remove.error.message}</p> : null}
    <ResourceReferenceList error={remove.error} />
  </Modal>
}
