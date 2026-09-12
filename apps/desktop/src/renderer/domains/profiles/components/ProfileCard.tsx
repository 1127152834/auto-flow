import { ArrowClockwise, Browser, Copy, PencilSimple, Play, Trash } from '@phosphor-icons/react'
import type { ProfileRead } from '../../../shared/api/types'
import { Badge } from '../../../shared/components/ui/badge'
import { Button } from '../../../shared/components/ui/button'

export type ProfileCardProps = {
  profile: ProfileRead
  disabled?: boolean
  regenerating?: boolean
  regenerationDisabled?: boolean
  launching?: boolean
  launchError?: string
  onOpen(profile: ProfileRead): void
  onEdit(profile: ProfileRead): void
  onDuplicate(profile: ProfileRead): void
  onRegenerate(profile: ProfileRead): void
  onDelete(profile: ProfileRead): void
}

const proxyLabels: Record<ProfileRead['proxyMode'], string> = {
  none: '不使用代理', proxy: '固定代理', pool: '代理池',
}

export function ProfileCard({ profile, disabled = false, regenerating = false, regenerationDisabled = false, launching = false, launchError, onOpen, onEdit, onDuplicate, onRegenerate, onDelete }: ProfileCardProps) {
  const busy = disabled || launching || regenerating
  return <li className="flex min-w-0 flex-col gap-5 rounded-card border border-line bg-surface p-5 shadow-sm">
    <div className="flex items-start gap-3">
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-control bg-surface-subtle text-clay"><Browser size={24} aria-hidden="true" /></div>
      <div className="min-w-0 flex-1">
        <h2 className="m-0 break-words text-base font-semibold text-ink">{profile.name}</h2>
        <p className="mb-0 mt-1 break-words text-sm leading-6 text-muted">{profile.description || '暂无描述'}</p>
      </div>
    </div>

    <div className="flex flex-wrap items-center justify-between gap-2 rounded-control border border-line bg-surface-subtle px-3 py-2.5">
      <div><span className="text-xs text-muted">指纹种子</span><span aria-label={`${profile.name} 的指纹种子`} aria-live="polite" className="ml-3 font-mono text-base font-semibold tabular-nums text-ink">{profile.fingerprintSeed}</span></div>
      <Button className="h-8 px-2 text-xs" variant="ghost" type="button" disabled={busy || regenerationDisabled} aria-label={`重新生成 ${profile.name} 的指纹`} onClick={() => onRegenerate(profile)}><ArrowClockwise className={regenerating ? 'motion-safe:animate-spin' : undefined} size={15} />{regenerating ? '生成中…' : '重置指纹'}</Button>
    </div>

    <dl className="m-0 grid grid-cols-2 gap-x-4 gap-y-4 text-xs">
      <div className="min-w-0"><dt className="text-muted">CloakBrowser 内核</dt><dd className="m-0 mt-1.5 flex flex-wrap items-center gap-1.5 text-ink"><span className="break-all font-medium">{profile.browserVersion}</span><Badge>{profile.browserEdition === 'licensed' ? '正式版' : '公开版'}</Badge><Badge className="bg-surface-subtle text-muted">{profile.releaseChannel === 'preview' ? '预览版' : '稳定版'}</Badge></dd></div>
      <div className="min-w-0"><dt className="text-muted">代理模式</dt><dd className="m-0 mt-1.5 text-sm text-ink">{proxyLabels[profile.proxyMode]}</dd></div>
      <div className="min-w-0"><dt className="text-muted">语言 / 时区</dt><dd className="m-0 mt-1.5 break-words leading-5 text-ink">{profile.locale || '跟随浏览器'} / {profile.timezone || '跟随浏览器'}</dd></div>
      <div className="min-w-0"><dt className="text-muted">视口</dt><dd className="m-0 mt-1.5 text-sm text-ink">{profile.viewportJson ? `${profile.viewportJson.width} × ${profile.viewportJson.height}` : '跟随窗口'}</dd></div>
    </dl>

    <div className="mt-auto border-t border-line pt-4">
      {launchError ? <p role="alert" className="mb-3 mt-0 break-words text-sm text-red-700">{launchError}</p> : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="primary" className="h-9 px-3" type="button" disabled={busy} aria-label={`打开 ${profile.name} 的测试浏览器`} onClick={() => onOpen(profile)}>{launching ? <ArrowClockwise className="motion-safe:animate-spin" size={16} /> : <Play size={16} weight="fill" />}{launching ? '正在打开…' : '打开测试浏览器'}</Button>
        <Button className="h-9 px-3" type="button" disabled={busy} aria-label={`编辑 ${profile.name}`} onClick={() => onEdit(profile)}><PencilSimple size={16} />编辑</Button>
        <div className="ml-auto flex gap-1">
          <Button className="h-9 px-2" variant="ghost" type="button" disabled={busy} aria-label={`复制 ${profile.name}`} title="复制配置" onClick={() => onDuplicate(profile)}><Copy size={17} /></Button>
          <Button className="h-9 px-2 text-red-700" variant="ghost" type="button" disabled={busy} aria-label={`删除 ${profile.name}`} title="删除配置" onClick={() => onDelete(profile)}><Trash size={17} /></Button>
        </div>
      </div>
      <p className="mb-0 mt-3 text-xs leading-5 text-muted">每次打开全新测试窗口，关闭后不保留浏览数据。</p>
    </div>
  </li>
}
