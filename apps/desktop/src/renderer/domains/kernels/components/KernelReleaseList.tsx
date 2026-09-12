import type { KernelOperation, KernelRef, KernelRelease } from '../../../shared/api/types'
import { Badge } from '../../../shared/components/ui/badge'
import { Button } from '../../../shared/components/ui/button'
import { KernelOperationStatus, operationIsActive } from './KernelOperationStatus'

export type KernelReleaseItem = Omit<KernelRelease, 'chromiumVersion' | 'releaseChannel'> & {
  chromiumVersion: string | null
  releaseChannel: KernelRelease['releaseChannel'] | null
  localOnly?: boolean
}

export type KernelReleaseListProps = {
  releases: readonly KernelReleaseItem[]
  defaultKernel?: KernelRef | null
  licensed: boolean
  operations?: readonly KernelOperation[]
  cancellingOperationIds?: ReadonlySet<string>
  cancellationErrors?: Readonly<Record<string, string>>
  pendingDownloadKeys?: ReadonlySet<string>
  downloadErrors?: Readonly<Record<string, string>>
  busy?: boolean
  disabled?: boolean
  canReveal?: boolean
  onDownload(release: KernelReleaseItem): void | Promise<void>
  onCancel(operationId: string): void | Promise<void>
  onRetry(operation: KernelOperation): void | Promise<void>
  onSetDefault(kernel: KernelRef | null): void | Promise<void>
  onReveal(kernel: KernelRef): void | Promise<void>
  onDelete(kernel: KernelRef, trigger: HTMLButtonElement): void
}

const keyOf = (value: KernelRef) => `${value.edition}|${value.version}`
const releaseKeyOf = (value: Pick<KernelReleaseItem, 'edition' | 'version' | 'releaseChannel'>) => `${keyOf(value)}|${value.releaseChannel ?? 'unknown'}`
const formatSize = (size: number | null) => size === null ? '未知' : `${(size / 1024 / 1024).toFixed(size >= 10 * 1024 * 1024 ? 0 : 1)} MB`

export function KernelReleaseList({ releases, defaultKernel, licensed, operations = [], cancellingOperationIds, cancellationErrors, pendingDownloadKeys, downloadErrors, busy = false, disabled = false, canReveal = true, onDownload, onCancel, onRetry, onSetDefault, onReveal, onDelete }: KernelReleaseListProps) {
  const operationByRelease = new Map<string, KernelOperation>()
  for (const operation of operations) operationByRelease.set(`${operation.edition}|${operation.requestedVersion}|${operation.releaseChannel}`, operation)

  if (!releases.length) return <p className="rounded-control border border-dashed border-line p-6 text-center text-sm text-muted">没有符合筛选条件的内核版本。</p>

  return <ul aria-label="内核版本卡片" className="m-0 grid list-none grid-cols-1 items-stretch gap-4 p-0 md:grid-cols-2">
    {releases.map((release) => {
      const kernel: KernelRef = { edition: release.edition, version: release.version }
      const isDefault = defaultKernel ? keyOf(defaultKernel) === keyOf(kernel) : false
      const operation = operationByRelease.get(releaseKeyOf(release))
      const operationActive = operation ? operationIsActive(operation) : false
      const pending = pendingDownloadKeys?.has(keyOf(kernel)) === true
      const targetActive = operations.some((item) => operationIsActive(item) && item.edition === kernel.edition
        && (item.requestedVersion === kernel.version || item.resolvedVersion === kernel.version))
      const targetBusy = pending || targetActive
      const locked = release.edition === 'licensed' && !licensed && !release.installed
      const downloadError = downloadErrors?.[keyOf(kernel)]
      return <li key={releaseKeyOf(release)} className="flex min-w-0 flex-col rounded-card border border-line bg-surface p-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <strong className="w-full break-words text-base text-ink">CloakBrowser {release.version}</strong>
              <Badge>{release.edition === 'licensed' ? '正式版' : '公开版'}</Badge>
              <Badge className="bg-surface-subtle text-muted">{release.releaseChannel === 'preview' ? 'Preview' : release.releaseChannel === 'stable' ? 'Stable' : '通道未知'}</Badge>
              {release.installed ? <Badge className="bg-sage-soft text-sage-strong">已安装</Badge> : null}
              {isDefault ? <Badge className="bg-blue-50 text-blue-800">默认</Badge> : null}
            </div>
            <dl className="mb-4 mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-xs text-muted">
              <div className="min-w-0"><dt>Chromium</dt><dd className="m-0 mt-1 break-words text-ink">{release.chromiumVersion ?? '未知'}</dd></div>
              <div className="min-w-0"><dt>发布日期</dt><dd className="m-0 mt-1 break-words text-ink">{release.publishedAt ?? '未知'}</dd></div>
              <div className="min-w-0"><dt>安装包</dt><dd className="m-0 mt-1 break-all text-ink">{release.archive ?? '未知'}</dd></div>
              <div className="min-w-0"><dt>大小</dt><dd className="m-0 mt-1 text-ink">{formatSize(release.size)}</dd></div>
            </dl>
            {release.localOnly ? <p className="mb-0 mt-2 text-xs text-muted">发布目录离线；这里只显示本机安装信息。</p> : null}
          </div>
          {downloadError ? <p role="alert" className="mb-3 mt-0 break-words text-sm text-red-700">{downloadError}</p> : null}
          {pending && !operationActive ? <p role="status" className="mb-3 mt-0 text-sm text-muted">正在创建下载任务…</p> : null}
          {operation ? <KernelOperationStatus operation={operation} cancelling={cancellingOperationIds?.has(operation.id)} cancellationError={cancellationErrors?.[operation.id]} disabled={disabled} retryDisabled={busy || locked || targetBusy} onCancel={() => onCancel(operation.id)} onRetry={() => onRetry(operation)} /> : null}
          <div className="mt-auto flex flex-wrap gap-2 border-t border-line pt-3">
            {release.installed ? <>
              <Button type="button" className="h-8 px-3" disabled={disabled || busy || targetBusy} onClick={() => void onSetDefault(isDefault ? null : kernel)}>{isDefault ? '取消默认' : '设为默认'}</Button>
              <Button type="button" className="h-8 px-3" disabled={disabled || busy || targetBusy || !canReveal} onClick={() => void onReveal(kernel)}>打开目录</Button>
              <Button type="button" variant="ghost" className="h-8 px-3 text-red-700" disabled={disabled || busy || targetBusy} onClick={(event) => onDelete(kernel, event.currentTarget)}>删除</Button>
            </> : operationActive || operation?.state === 'failed' ? null : <Button type="button" variant="primary" className="h-8 px-3" disabled={disabled || busy || locked || targetBusy} onClick={() => void onDownload(release)}>{locked ? '需要 License' : targetBusy ? '处理中…' : downloadError ? '重试下载' : '下载安装'}</Button>}
          </div>
      </li>
    })}
  </ul>
}
