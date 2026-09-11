import { MagnifyingGlass, Plus } from '@phosphor-icons/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { KernelRef, ProfileRead } from '../../../shared/api/types'
import { notify, Toaster } from '../../../shared/components/Toaster'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { KernelManagerDialog } from '../../kernels/components/KernelManagerDialog'
import { ProfileActionDialog, type ProfileAction } from '../components/ProfileActionDialog'
import { ProfileFormDialog } from '../components/ProfileFormDialog'
import { ProfileList } from '../components/ProfileList'
import { useProfiles, useRegenerateProfile } from '../hooks'

export type BrowserManagementPageProps = {
  disabled?: boolean
  onReconnect?(): void
}

type ProxyFilter = 'all' | ProfileRead['proxyMode']
const PAGE_SIZE = 10
const errorMessage = (error: unknown) => error instanceof Error ? error.message : '操作失败，请重试'

export function BrowserManagementPage({ disabled = false, onReconnect }: BrowserManagementPageProps) {
  const profiles = useProfiles()
  const regenerate = useRegenerateProfile()
  const [query, setQuery] = useState('')
  const [proxyFilter, setProxyFilter] = useState<ProxyFilter>('all')
  const [page, setPage] = useState(1)
  const [formOpen, setFormOpen] = useState(false)
  const [formProfile, setFormProfile] = useState<ProfileRead | null>(null)
  const [action, setAction] = useState<ProfileAction | null>(null)
  const [kernelOpen, setKernelOpen] = useState(false)
  const [selectedKernel, setSelectedKernel] = useState<KernelRef | null>(null)
  const kernelTrigger = useRef<HTMLButtonElement | null>(null)
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase()
    return (profiles.data?.items ?? []).filter((profile) => {
      const matchesText = !needle || `${profile.name}\n${profile.description}`.toLocaleLowerCase().includes(needle)
      return matchesText && (proxyFilter === 'all' || profile.proxyMode === proxyFilter)
    })
  }, [profiles.data?.items, proxyFilter, query])
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const visibleProfiles = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  useEffect(() => { setPage((current) => Math.min(current, pageCount)) }, [pageCount])

  function openForm(profile: ProfileRead | null) {
    setFormProfile(profile)
    setFormOpen(true)
  }

  async function regenerateFingerprint(profile: ProfileRead) {
    if (disabled || regeneratingId) return
    setRegeneratingId(profile.id)
    try {
      await regenerate.mutateAsync(profile.id)
      notify({ title: '指纹已重新生成', tone: 'success' })
    } catch (error) {
      notify({ title: errorMessage(error), tone: 'error' })
    } finally {
      setRegeneratingId(null)
    }
  }

  const hasProfiles = Boolean(profiles.data?.items.length)
  const initialError = profiles.isError && !profiles.data

  return <main className="min-h-dvh min-w-0 bg-canvas px-4 py-6 text-ink sm:px-6 lg:px-8">
    <div className="mx-auto grid w-full max-w-[1480px] min-w-0 gap-5">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="m-0 text-2xl font-semibold tracking-tight text-ink">浏览器配置</h1>
          <p className="mb-0 mt-1 text-sm text-muted">管理固定指纹环境，组合 CloakBrowser 内核和代理资源。</p>
        </div>
        <Button type="button" variant="primary" disabled={disabled} onClick={() => openForm(null)}><Plus size={18} weight="bold" />新建配置</Button>
      </header>

      <section aria-label="配置筛选" className="grid gap-3 rounded-card border border-line bg-surface p-4 sm:grid-cols-[minmax(0,1fr)_13rem]">
        <label className="relative min-w-0">
          <span className="sr-only">搜索配置</span>
          <MagnifyingGlass aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={18} />
          <Input type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="搜索配置名称或描述" className="w-full pl-10" />
        </label>
        <Select aria-label="代理模式筛选" value={proxyFilter} onChange={(event) => { setProxyFilter(event.target.value as ProxyFilter); setPage(1) }} className="w-full">
          <option value="all">全部代理模式</option>
          <option value="none">不使用代理</option>
          <option value="proxy">固定代理</option>
          <option value="pool">代理池</option>
        </Select>
      </section>

      {profiles.isFetching && profiles.data ? <p role="status" className="m-0 text-xs text-muted">正在同步本地数据…</p> : null}
      {profiles.isError && profiles.data ? <div role="alert" className="flex flex-col gap-3 rounded-control border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 sm:flex-row sm:items-center sm:justify-between"><span>{errorMessage(profiles.error)}。已加载的数据会继续保留。</span><Button type="button" onClick={() => void profiles.refetch()}>重试</Button></div> : null}

      {profiles.isPending ? <div className="grid animate-pulse gap-3" role="status" aria-label="正在加载浏览器配置">{[1, 2, 3].map((item) => <div key={item} className="h-36 rounded-card bg-surface-subtle" />)}<span className="sr-only">正在同步本地数据，请稍候…</span></div>
        : initialError ? <section role="alert" className="rounded-card border border-red-200 bg-red-50 p-6"><h2 className="m-0 text-lg">浏览器配置加载失败</h2><p className="text-sm text-red-800">{errorMessage(profiles.error)}</p><Button type="button" onClick={() => void profiles.refetch()}>重试</Button></section>
        : !hasProfiles ? <section role="status" className="rounded-card border border-dashed border-line-strong bg-surface p-10 text-center"><h2 className="m-0 text-lg font-semibold">还没有浏览器配置</h2><p className="mb-0 mt-2 text-sm text-muted">创建第一个固定指纹环境。</p><Button type="button" className="mt-5" variant="primary" disabled={disabled} onClick={() => openForm(null)}><Plus size={18} />新建配置</Button></section>
        : !filtered.length ? <section role="status" className="rounded-card border border-dashed border-line-strong bg-surface p-8 text-center"><h2 className="m-0 text-base font-semibold">没有匹配的配置</h2><p className="mb-0 mt-2 text-sm text-muted">调整搜索内容或代理模式筛选。</p></section>
        : <>
          <ProfileList profiles={visibleProfiles} disabled={disabled} regeneratingId={regeneratingId} onEdit={(profile) => openForm(profile)} onDuplicate={(profile) => setAction({ kind: 'duplicate', id: profile.id, name: profile.name })} onRegenerate={(profile) => void regenerateFingerprint(profile)} onDelete={(profile) => setAction({ kind: 'delete', id: profile.id, name: profile.name })} />
          <footer className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted">
            <span>共 {filtered.length} 个配置</span>
            <div className="flex items-center gap-3">
              <Button type="button" className="h-8 px-3" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>上一页</Button>
              <span aria-live="polite">第 {page} / {pageCount} 页</span>
              <Button type="button" className="h-8 px-3" disabled={page >= pageCount} onClick={() => setPage((current) => current + 1)}>下一页</Button>
            </div>
          </footer>
        </>}
    </div>

    <ProfileFormDialog open={formOpen} onOpenChange={setFormOpen} initialProfile={formProfile} disabled={disabled} onReconnect={onReconnect} onManageKernel={(kernel, trigger) => {
      setSelectedKernel(kernel)
      kernelTrigger.current = trigger
      setKernelOpen(true)
    }} />
    <KernelManagerDialog open={kernelOpen} onOpenChange={setKernelOpen} selectedKernel={selectedKernel} returnFocusTo={kernelTrigger.current} disabled={disabled} onReconnect={onReconnect} />
    {action ? <ProfileActionDialog key={`${action.kind}:${action.id}`} action={action} disabled={disabled} onReconnect={onReconnect} onClose={(deleted) => {
      if (deleted && visibleProfiles.length === 1 && page > 1) setPage((current) => current - 1)
      setAction(null)
    }} /> : null}
    <Toaster />
  </main>
}
