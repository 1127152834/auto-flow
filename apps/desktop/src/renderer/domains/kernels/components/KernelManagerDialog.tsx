import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useMemo, useRef, useState } from 'react'
import { useApi } from '../../../app/ApiProvider'
import { ApiClientError } from '../../../shared/api/client'
import type { KernelOperation, KernelRef } from '../../../shared/api/types'
import { notify } from '../../../shared/components/Toaster'
import { Button } from '../../../shared/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '../../../shared/components/ui/dialog'
import {
  kernelKeys,
  upsertKernelOperation,
  useCancelKernelDownload,
  useCheckKernelUpdate,
  useConnectKernelLicense,
  useDefaultKernel,
  useDisconnectKernelLicense,
  useDownloadKernel,
  useInstalledKernels,
  useKernelCatalog,
  useKernelEvents,
  useKernelLicense,
  useRemoveKernel,
  useSetDefaultKernel,
} from '../hooks'
import { DeleteKernelDialog } from './DeleteKernelDialog'
import { KernelReleaseList, type KernelReleaseItem } from './KernelReleaseList'
import { LicensePanel } from './LicensePanel'
import { KernelOperationStatus, operationIsActive } from './KernelOperationStatus'

export type KernelManagerDialogProps = {
  open: boolean
  onOpenChange(open: boolean): void
  selectedKernel: KernelRef | null
  returnFocusTo?: HTMLButtonElement | null
  disabled?: boolean
  onReconnect?(): void
}

type Filter = 'all' | 'public' | 'licensed' | 'installed'
const filters: readonly [Filter, string][] = [['all', '全部版本'], ['public', '公开版'], ['licensed', '正式版'], ['installed', '已安装']]
const keyOf = (value: KernelRef) => `${value.edition}|${value.version}`
const releaseKeyOf = (value: Pick<KernelReleaseItem, 'edition' | 'version' | 'releaseChannel'>) => `${keyOf(value)}|${value.releaseChannel ?? 'unknown'}`
const message = (error: unknown) => error instanceof Error ? error.message : '操作未完成，请稍后重试'

export function KernelManagerDialog({ open, onOpenChange, selectedKernel, returnFocusTo, disabled = false, onReconnect }: KernelManagerDialogProps) {
  const { instanceId } = useApi()
  const queryClient = useQueryClient()
  const catalog = useKernelCatalog()
  const installed = useInstalledKernels()
  const license = useKernelLicense()
  const defaultQuery = useDefaultKernel()
  const connect = useConnectKernelLicense()
  const disconnect = useDisconnectKernelLicense()
  const download = useDownloadKernel()
  const cancel = useCancelKernelDownload()
  const setDefault = useSetDefaultKernel()
  const remove = useRemoveKernel()
  const checkUpdate = useCheckKernelUpdate()
  const operations = useQuery<KernelOperation[]>({ queryKey: kernelKeys.operations(instanceId), queryFn: async () => [], enabled: false })
  const [filter, setFilter] = useState<Filter>('all')
  const [actionError, setActionError] = useState<string | null>(null)
  const [licenseError, setLicenseError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<KernelRef | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [cancellingOperationId, setCancellingOperationId] = useState<string | null>(null)
  const deleteTrigger = useRef<HTMLButtonElement | null>(null)
  const notifiedTerminalIds = useRef(new Set<string>())

  const terminal = useCallback((operation: KernelOperation) => {
    if (notifiedTerminalIds.current.has(operation.id)) return
    notifiedTerminalIds.current.add(operation.id)
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: kernelKeys.installed(instanceId) }),
      queryClient.invalidateQueries({ queryKey: kernelKeys.catalog(instanceId) }),
    ])
    setCancellingOperationId((current) => current === operation.id ? null : current)
    notify({
      title: operation.state === 'completed' ? '内核安装完成' : operation.state === 'cancelled' ? '内核安装已取消' : operation.error ?? '内核安装失败',
      tone: operation.state === 'completed' ? 'success' : operation.state === 'cancelled' ? 'info' : 'error',
    })
  }, [instanceId, queryClient])
  useKernelEvents({ onTerminal: terminal })

  const localKernels = useMemo(() => {
    return installed.data?.items ?? catalog.data?.installed ?? []
  }, [catalog.data?.installed, installed.data?.items])

  const releases = useMemo<KernelReleaseItem[]>(() => {
    const local = new Map(localKernels.map((item) => [keyOf(item), item]))
    const values = new Map<string, KernelReleaseItem>()
    for (const release of catalog.data?.releases ?? []) values.set(releaseKeyOf(release), {
      ...release,
      installed: local.has(keyOf(release)),
    })
    for (const item of localKernels) if (![...values.values()].some((release) => keyOf(release) === keyOf(item))) values.set(`${keyOf(item)}|unknown`, {
      edition: item.edition,
      version: item.version,
      chromiumVersion: null,
      releaseChannel: null,
      publishedAt: null,
      archive: null,
      size: item.size,
      installed: true,
      localOnly: true,
    })
    return [...values.values()]
  }, [catalog.data?.releases, localKernels])

  const visibleReleases = releases.filter((release) => filter === 'all' || (filter === 'installed' ? release.installed : release.edition === filter))
  const activeOperation = (operations.data ?? []).some(operationIsActive)
  const hiddenActiveOperations = (operations.data ?? []).filter((operation) => operationIsActive(operation)
    && !visibleReleases.some((release) => release.edition === operation.edition && release.version === operation.requestedVersion && release.releaseChannel === operation.releaseChannel))
  const busy = activeOperation || download.isPending || remove.isPending || setDefault.isPending || connect.isPending || disconnect.isPending
  const licensed = license.data?.configured === true && license.data.valid
  const selectedUnavailable = Boolean(selectedKernel && (installed.data || catalog.data) && !localKernels.some((item) => keyOf(item) === keyOf(selectedKernel)))

  function changeOpen(nextOpen: boolean) {
    if (!nextOpen) {
      if (busy) return
      void queryClient.invalidateQueries({ queryKey: kernelKeys.installed(instanceId) })
      onOpenChange(false)
      if (returnFocusTo) window.requestAnimationFrame(() => returnFocusTo.focus())
      return
    }
    onOpenChange(true)
  }

  async function startDownload(release: KernelReleaseItem) {
    if (disabled) return
    setActionError(null)
    if (!release.releaseChannel) { setActionError('该本机内核没有可用的发布通道信息。'); return }
    try {
      await download.mutateAsync({ edition: release.edition, version: release.version, releaseChannel: release.releaseChannel })
    } catch (error) {
      setActionError(message(error))
    }
  }

  async function retryDownload(operation: KernelOperation) {
    if (disabled) return
    setActionError(null)
    try {
      await download.mutateAsync({ edition: operation.edition, version: operation.requestedVersion, releaseChannel: operation.releaseChannel })
    } catch (error) {
      setActionError(message(error))
    }
  }

  async function cancelDownload(operationId: string) {
    if (disabled) return
    setActionError(null)
    setCancellingOperationId(operationId)
    try {
      const value = await cancel.mutateAsync(operationId)
      queryClient.setQueryData<KernelOperation[]>(kernelKeys.operations(instanceId), (current = []) => upsertKernelOperation(current, value))
      if (!operationIsActive(value)) { setCancellingOperationId(null); terminal(value) }
    } catch (error) {
      setCancellingOperationId(null)
      setActionError(message(error))
    }
  }

  async function changeDefault(kernel: KernelRef | null) {
    if (disabled) return
    if (!defaultQuery.data) return
    setActionError(null)
    try {
      await setDefault.mutateAsync({ expectedRevision: defaultQuery.data.revision, kernel })
      notify({ title: kernel ? '默认内核已更新' : '已取消默认内核', tone: 'success' })
    } catch (error) {
      if (error instanceof ApiClientError && error.code === 'KERNEL_DEFAULT_CONFLICT') {
        await defaultQuery.refetch()
        setActionError('默认内核已被其他操作更新，已刷新当前状态。')
      } else setActionError(message(error))
    }
  }

  async function reveal(kernel: KernelRef) {
    if (disabled) return
    setActionError(null)
    try {
      if (!window.autoflow?.revealKernel) throw new Error('当前环境不支持打开内核目录')
      await window.autoflow.revealKernel(kernel)
    } catch (error) {
      setActionError(message(error))
    }
  }

  async function confirmDelete(kernel: KernelRef) {
    if (disabled) return
    setDeleteError(null)
    try {
      await remove.mutateAsync(kernel)
      setDeleteTarget(null)
      notify({ title: '内核已删除', tone: 'success' })
    } catch (error) {
      setDeleteError(message(error))
    }
  }

  return <>
    <Dialog open={open} onOpenChange={changeOpen} busy={busy}>
      <DialogContent className="max-h-[90vh] w-[min(94vw,64rem)] overflow-y-auto" onCloseAutoFocus={(event) => {
        if (returnFocusTo) { event.preventDefault(); returnFocusTo.focus() }
      }}>
        <div className="flex items-start justify-between gap-4">
          <div><DialogTitle>CloakBrowser 内核管理</DialogTitle><DialogDescription className="mt-1">下载和管理本机唯一支持的浏览器运行时。</DialogDescription></div>
          <Button type="button" variant="ghost" aria-label="关闭内核管理" disabled={busy} onClick={() => changeOpen(false)}>关闭</Button>
        </div>

        {disabled ? <div role="alert" className="flex flex-col gap-3 rounded-control border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 sm:flex-row sm:items-center sm:justify-between"><span>本地服务离线，内核操作已暂停。重新连接后请手动重试。</span>{onReconnect ? <Button type="button" onClick={onReconnect}>重新连接</Button> : null}</div> : null}

        <LicensePanel status={license.data} busy={connect.isPending || disconnect.isPending} disabled={disabled} error={licenseError ?? (license.error ? message(license.error) : null)} onConnect={async (licenseKey) => {
          setLicenseError(null)
          try { await connect.mutateAsync({ licenseKey }); notify({ title: 'License 已登录', tone: 'success' }) }
          catch (error) { setLicenseError(message(error)); throw error }
        }} onDisconnect={async () => {
          setLicenseError(null)
          try { await disconnect.mutateAsync(); notify({ title: 'License 已退出', tone: 'success' }) }
          catch (error) { setLicenseError(message(error)); throw error }
        }} />

        <section aria-labelledby="kernel-release-title" className="grid gap-4">
          {hiddenActiveOperations.length ? <section aria-label="活动内核下载">
            {hiddenActiveOperations.map((operation) => <div key={operation.id}>
              <h3 className="mb-0 text-sm font-semibold">CloakBrowser {operation.requestedVersion} · {operation.edition === 'licensed' ? '正式版' : '公开版'} · {operation.releaseChannel === 'preview' ? 'Preview' : 'Stable'}</h3>
              <KernelOperationStatus operation={operation} cancelling={cancellingOperationId === operation.id} disabled={disabled} onCancel={() => cancelDownload(operation.id)} />
            </div>)}
          </section> : null}
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div><h3 id="kernel-release-title" className="m-0 text-base font-semibold text-ink">版本列表</h3><p className="mb-0 mt-1 text-xs text-muted">Wrapper {catalog.data?.wrapperVersion ?? '未知'} · 本机已安装 {localKernels.length} 个</p></div>
            <Button type="button" disabled={disabled || checkUpdate.isPending} onClick={() => { if (disabled) return; setActionError(null); void checkUpdate.mutateAsync().catch((error) => setActionError(message(error))) }}>{checkUpdate.isPending ? '正在刷新…' : '刷新版本列表'}</Button>
          </div>
          <div className="flex flex-wrap gap-2" aria-label="内核版本筛选">
            {filters.map(([value, label]) => <Button key={value} type="button" variant={filter === value ? 'primary' : 'secondary'} className="h-8 px-3" aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</Button>)}
          </div>
          {catalog.error || catalog.data?.catalogError ? <p role="alert" className="m-0 rounded-control border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">发布列表暂不可用：{catalog.data?.catalogError ?? message(catalog.error)}。仍可管理本机已安装内核。</p> : null}
          {selectedUnavailable ? <p role="alert" className="m-0 rounded-control border border-red-200 bg-red-50 p-3 text-sm text-red-800">当前表单选择的内核已不可用；原选择值会保留，请改选已安装内核后再保存。</p> : null}
          {actionError ? <p role="alert" className="m-0 rounded-control border border-red-200 bg-red-50 p-3 text-sm text-red-800">{actionError}</p> : null}
          {catalog.isLoading && installed.isLoading ? <p role="status" className="py-6 text-center text-sm text-muted">正在同步本地数据，请稍候…</p> : <KernelReleaseList releases={visibleReleases} defaultKernel={defaultQuery.data?.kernel} licensed={licensed} operations={operations.data} cancellingOperationId={cancellingOperationId} busy={busy} disabled={disabled} canReveal={typeof window.autoflow?.revealKernel === 'function'} onDownload={startDownload} onCancel={cancelDownload} onRetry={retryDownload} onSetDefault={changeDefault} onReveal={reveal} onDelete={(kernel, trigger) => { if (disabled) return; deleteTrigger.current = trigger; setDeleteError(null); setDeleteTarget(kernel) }} />}
        </section>
      </DialogContent>
    </Dialog>
    <DeleteKernelDialog kernel={deleteTarget} busy={remove.isPending} disabled={disabled} error={deleteError} onReconnect={onReconnect} returnFocusTo={deleteTrigger.current} onOpenChange={(nextOpen) => { if (!nextOpen) setDeleteTarget(null) }} onConfirm={confirmDelete} />
  </>
}
