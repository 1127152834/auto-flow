import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Modal } from '../../../shared/components/Modal'
import { Button } from '../../../shared/components/ui/button'
import type { ModelApi } from '../api'
import { refreshAfterModelConflict } from '../cache'
import type { ModelProvider } from '../model'

export function ProviderDeleteDialog({ provider, api, instanceId, blocked, onClose, onRemoved }: {
  provider: ModelProvider; api: ModelApi; instanceId: string; blocked: boolean; onClose(): void; onRemoved(): void
}) {
  const cache = useQueryClient()
  const remove = useMutation({ mutationFn: () => api.removeProvider(provider.id), retry: false, onError: error => refreshAfterModelConflict(cache, instanceId, error), onSuccess: () => { onRemoved(); onClose() } })
  return <Modal open onOpenChange={open => { if (!open) onClose() }} closeDisabled={remove.isPending} size="small" title="删除供应商" description={`确认删除“${provider.name}”？`} footer={<>
    <Button disabled={remove.isPending} onClick={onClose}>取消</Button>
    <Button variant="danger" disabled={blocked || remove.isPending} onClick={() => remove.mutate()}>{remove.isPending ? '正在删除…' : '确认删除'}</Button>
  </>}>
    <p>同时移除该供应商下的 {provider.models.length} 个本地模型配置。此操作无法撤销，不影响供应商的远端账号。</p>
    {remove.error && <p role="alert" className="text-danger">{remove.error.message}</p>}
  </Modal>
}
