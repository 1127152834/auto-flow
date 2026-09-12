import type { ProfileRead, ProfileTestBrowserList } from '../../../shared/api/types'
import { ProfileCard } from './ProfileCard'

export type ProfileListProps = {
  profiles: readonly ProfileRead[]
  disabled?: boolean
  regeneratingId?: string | null
  browserSessions?: ProfileTestBrowserList
  browserStatusUnavailable?: boolean
  closingIds?: ReadonlySet<string>
  onClose(profile: ProfileRead): void
  launchingIds?: ReadonlySet<string>
  launchErrors?: Readonly<Record<string, string>>
  onOpen(profile: ProfileRead): void
  onEdit(profile: ProfileRead): void
  onDuplicate(profile: ProfileRead): void
  onRegenerate(profile: ProfileRead): void
  onDelete(profile: ProfileRead): void
}

export function ProfileList({ profiles, regeneratingId, launchingIds, closingIds, browserSessions, launchErrors, ...actions }: ProfileListProps) {
  return <ul aria-label="浏览器配置列表" className="m-0 grid list-none grid-cols-1 items-stretch gap-5 p-0 md:grid-cols-2">
    {profiles.map((profile) => <ProfileCard key={profile.id} profile={profile} regenerating={regeneratingId === profile.id} regenerationDisabled={Boolean(regeneratingId)} launching={launchingIds?.has(profile.id)} closing={closingIds?.has(profile.id)} browserState={browserSessions?.items.find((item) => item.profileId === profile.id)?.state} launchError={launchErrors?.[profile.id]} {...actions} />)}
  </ul>
}
