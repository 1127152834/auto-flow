import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Fingerprint } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { StreamingApiClient } from '../../shared/api/client'
import { notify } from '../../shared/components/Toaster'
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from '../../shared/components/ui/alert-dialog'
import { Button } from '../../shared/components/ui/button'
import { EmptyState } from '../../shared/components/ui/empty-state'
import { Input } from '../../shared/components/ui/input'
import { safeProjectError } from '../projects/presentation-error'
import { createIdentityApi, type Identity } from './api'

/**
 * Remediation M4 R4-09: the accounts of a project, each with its own fingerprint. The raw
 * seed never reaches the page; a short fingerprint label tells identities apart.
 */
export function IdentityDirectory({ client, projectId, scope, disabled }: {
  client: StreamingApiClient
  projectId: string
  scope: readonly unknown[]
  disabled: boolean
}) {
  const api = useMemo(() => createIdentityApi(client, projectId), [client, projectId])
  const cache = useQueryClient()
  const key = [...scope, 'identities', projectId] as const
  const identities = useQuery({ queryKey: key, queryFn: ({ signal }) => api.list(signal), enabled: !disabled })
  const [name, setName] = useState('')
  const [draftKey, setDraftKey] = useState(() => crypto.randomUUID())
  const [regenerating, setRegenerating] = useState<Identity | null>(null)
  const refresh = () => void cache.invalidateQueries({ queryKey: key })
  const fail = (error: unknown) => notify({ title: safeProjectError(error), tone: 'error' })
  const create = useMutation({
    mutationFn: () => api.create(name, draftKey),
    onSuccess: () => { setName(''); setDraftKey(crypto.randomUUID()); refresh() },
    onError: fail,
  })
  const regenerate = useMutation({
    mutationFn: (identity: Identity) => api.regenerateSeed(identity.identityId),
    onSuccess: () => { setRegenerating(null); notify({ title: '已换用新的指纹', tone: 'success' }); refresh() },
    onError: fail,
  })
  const reset = useMutation({ mutationFn: (identity: Identity) => api.resetHealth(identity.identityId), onSuccess: refresh, onError: fail })
  const remove = useMutation({ mutationFn: (identity: Identity) => api.remove(identity.identityId), onSuccess: refresh, onError: fail })
  const items = identities.data?.items ?? []
  return <section className="grid gap-4" aria-label="身份">
    <form className="flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); if (name.trim()) create.mutate() }}>
      <label className="grid gap-1 text-sm"><span className="font-medium">新身份名称</span>
        <Input className="w-64" aria-label="新身份名称" value={name} disabled={disabled || create.isPending} onChange={event => setName(event.target.value)} placeholder="例如：店铺账号 01" />
      </label>
      <Button type="submit" disabled={disabled || create.isPending || !name.trim()}>新建身份</Button>
      <p className="m-0 basis-full text-xs text-muted">每个身份有自己的浏览器指纹，新建时自动分配，与其他身份都不相同。</p>
    </form>
    {identities.isError ? <p role="alert" className="m-0 text-sm">无法读取身份。{safeProjectError(identities.error)}</p> : null}
    {identities.data && !items.length ? <EmptyState icon={<Fingerprint size={32} />} title="还没有身份" description="为每个账号新建一个身份，任务会用它固定的指纹、地区和登录状态运行。" /> : null}
    {items.length ? <table className="w-full border-collapse text-sm">
      <thead><tr className="text-left text-xs text-muted"><th className="py-2 font-medium">名称</th><th className="font-medium">指纹</th><th className="font-medium">登录状态</th><th className="font-medium">状态</th><th className="font-medium"><span className="sr-only">操作</span></th></tr></thead>
      <tbody>{items.map(identity => <tr key={identity.identityId} className="border-t border-line">
        <td className="py-2 [overflow-wrap:anywhere]">{identity.name}</td>
        <td><code className="text-xs">{identity.seedFingerprint}</code>{identity.legacySharedSeed ? <span className="ml-2 text-xs text-warning">与其他身份共用旧指纹</span> : null}</td>
        <td>{identity.environmentId ? '已保存' : '未保存'}</td>
        <td>{identity.health.banned ? '已封禁' : identity.health.consecutiveFailures ? `连续登录失败 ${identity.health.consecutiveFailures} 次` : '正常'}</td>
        <td className="whitespace-nowrap text-right">
          <Button size="sm" variant="ghost" disabled={disabled} onClick={() => setRegenerating(identity)}>换新指纹</Button>
          {identity.health.banned || identity.health.consecutiveFailures ? <Button size="sm" variant="ghost" disabled={disabled || reset.isPending} onClick={() => reset.mutate(identity)}>恢复正常</Button> : null}
          <Button size="sm" variant="ghost" disabled={disabled || remove.isPending || Boolean(identity.environmentId)} onClick={() => remove.mutate(identity)}>删除</Button>
        </td>
      </tr>)}</tbody>
    </table> : null}
    <AlertDialog open={Boolean(regenerating)} onOpenChange={open => { if (!open && !regenerate.isPending) setRegenerating(null) }}><AlertDialogContent>
      <AlertDialogTitle>为「{regenerating?.name}」换新指纹</AlertDialogTitle>
      <AlertDialogDescription>网站会把它当作一台新设备，已登录的账号可能需要重新验证。旧指纹不会再分配给任何身份。</AlertDialogDescription>
      <div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button disabled={regenerate.isPending}>取消</Button></AlertDialogCancel><Button variant="danger" disabled={regenerate.isPending} onClick={() => regenerating && regenerate.mutate(regenerating)}>换新指纹</Button></div>
    </AlertDialogContent></AlertDialog>
  </section>
}
