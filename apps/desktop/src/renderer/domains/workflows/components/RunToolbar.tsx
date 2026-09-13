import type { ReactNode } from 'react'
import { Play, Stop } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'
import type { ProfileRead } from '../../../shared/api/types'
import { runStateLabel, type RunRead } from '../run-types'

type Props = {
  resource?: ReactNode; resourceReady?: boolean
  profiles: ProfileRead[]; profileId: string; onProfileChange(id: string): void
  active: RunRead | null; busy: boolean; uncertain: boolean; disabled: boolean
  profilesLoading: boolean; profilesError: boolean
  onStart(): void; onStop(): void; onRefresh(): void
  canRetryStart?: boolean; onRetryStart?(): void
}

export function RunToolbar({ resource, resourceReady, profiles, profileId, onProfileChange, active, busy, uncertain, disabled, profilesLoading, profilesError, onStart, onStop, onRefresh, canRetryStart, onRetryStart }: Props) {
  return <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-line bg-surface px-5 py-2.5" aria-label="流程运行控制">
    {resource ?? <><label htmlFor="run-profile" className="text-xs font-medium text-muted">浏览器配置</label>
    <Select id="run-profile" className="h-9 w-48" value={profileId} disabled={disabled || busy || Boolean(active)} onChange={event => onProfileChange(event.target.value)}>
      <option value="">{profilesLoading ? '正在读取配置…' : profiles.length ? '选择浏览器配置' : '请先创建浏览器配置'}</option>
      {profiles.map(profile => <option key={profile.id} value={profile.id}>{profile.name}{profile.headless ? ' · 无头' : ''}</option>)}
    </Select></>}
    <Button variant="primary" className="h-9" disabled={disabled || busy || uncertain || Boolean(active) || !(resourceReady ?? (Boolean(profileId) && profiles.some(profile => profile.id === profileId)))} onClick={onStart}><Play size={15} />运行当前草稿</Button>
    <Button className="h-9" disabled={disabled || busy || (!active && !uncertain)} onClick={onStop}><Stop size={15} />停止</Button>
    {active ? <span role="status" className="text-xs text-muted">{runStateLabel[active.state]} · {active.completedNodeIds.length}/{active.nodeOrder.length} 步 · {active.targetName ?? active.profileName}</span> : <span className="text-xs text-muted">运行不会保存草稿</span>}
    {uncertain ? <span role="status" className="text-xs text-amber-800">正在核实运行状态，尚未允许再次启动</span> : null}
    {canRetryStart ? <Button className="h-8 text-xs" disabled={disabled || busy} onClick={onRetryStart}>按原编号重试启动</Button> : null}
    {profilesError && !resource ? <span role="alert" className="text-xs text-red-700">浏览器配置读取失败</span> : null}
    <Button variant="ghost" className="ml-auto h-8 text-xs" disabled={disabled || busy} onClick={onRefresh}>刷新运行状态</Button>
  </div>
}
