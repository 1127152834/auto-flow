import { ArrowClockwise, Copy, PencilSimple, Trash } from '@phosphor-icons/react'
import type { ProfileRead } from '../../../shared/api/types'
import { Badge } from '../../../shared/components/ui/badge'
import { Button } from '../../../shared/components/ui/button'

export type ProfileListProps = {
  profiles: readonly ProfileRead[]
  disabled?: boolean
  regeneratingId?: string | null
  onEdit(profile: ProfileRead): void
  onDuplicate(profile: ProfileRead): void
  onRegenerate(profile: ProfileRead): void
  onDelete(profile: ProfileRead): void
}

const proxyLabels: Record<ProfileRead['proxyMode'], string> = {
  none: '不使用代理',
  proxy: '固定代理',
  pool: '代理池',
}

export function ProfileList({ profiles, disabled = false, regeneratingId, onEdit, onDuplicate, onRegenerate, onDelete }: ProfileListProps) {
  return <ul aria-label="浏览器配置列表" className="m-0 grid list-none gap-3 p-0">
    {profiles.map((profile) => {
      const regenerating = regeneratingId === profile.id
      return <li key={profile.id} className="min-w-0 rounded-card border border-line bg-surface p-4 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="m-0 break-words text-base font-semibold text-ink">{profile.name}</h2>
              <Badge>{profile.browserEdition === 'licensed' ? '正式版' : '公开版'}</Badge>
              <Badge className="bg-surface-subtle text-muted">{profile.releaseChannel === 'preview' ? 'Preview' : 'Stable'}</Badge>
            </div>
            <p className="mb-0 mt-1 break-words text-sm text-muted">{profile.description || '暂无描述'}</p>
          </div>
          <div className="flex flex-wrap gap-1 xl:justify-end">
            <Button className="h-8 px-2.5" type="button" disabled={disabled} aria-label={`编辑 ${profile.name}`} onClick={() => onEdit(profile)}><PencilSimple size={16} />编辑</Button>
            <Button className="h-8 px-2.5" type="button" disabled={disabled} aria-label={`复制 ${profile.name}`} onClick={() => onDuplicate(profile)}><Copy size={16} />复制</Button>
            <Button className="h-8 px-2.5" type="button" disabled={disabled || Boolean(regeneratingId)} aria-label={`重新生成 ${profile.name} 的指纹`} onClick={() => onRegenerate(profile)}><ArrowClockwise className={regenerating ? 'motion-safe:animate-spin motion-safe:[animation-duration:300ms]' : undefined} size={16} />{regenerating ? '生成中…' : '重新生成指纹'}</Button>
            <Button className="h-8 px-2.5 text-red-700" variant="ghost" type="button" disabled={disabled} aria-label={`删除 ${profile.name}`} onClick={() => onDelete(profile)}><Trash size={16} />删除</Button>
          </div>
        </div>
        <dl className="mb-0 mt-4 grid gap-3 border-t border-line pt-4 text-xs sm:grid-cols-2 lg:grid-cols-4">
          <div className="min-w-0"><dt className="text-muted">指纹种子</dt><dd className="m-0 mt-1 break-all font-mono text-ink">{profile.fingerprintSeed}</dd></div>
          <div className="min-w-0"><dt className="text-muted">CloakBrowser 内核</dt><dd className="m-0 mt-1 break-all text-ink">{profile.browserVersion}</dd></div>
          <div className="min-w-0"><dt className="text-muted">语言 / 时区</dt><dd className="m-0 mt-1 break-words text-ink">{profile.locale || '跟随浏览器'} / {profile.timezone || '跟随浏览器'}</dd></div>
          <div className="min-w-0"><dt className="text-muted">代理模式</dt><dd className="m-0 mt-1 break-words text-ink">{proxyLabels[profile.proxyMode]}</dd></div>
        </dl>
      </li>
    })}
  </ul>
}
