import type { ProfileRead } from '../../../shared/api/types'
import { ProfileCard } from './ProfileCard'

export type ProfileListProps = {
  profiles: readonly ProfileRead[]
  disabled?: boolean
  regeneratingId?: string | null
  launchingIds?: ReadonlySet<string>
  launchErrors?: Readonly<Record<string, string>>
  onOpen(profile: ProfileRead): void
  onEdit(profile: ProfileRead): void
  onDuplicate(profile: ProfileRead): void
  onRegenerate(profile: ProfileRead): void
  onDelete(profile: ProfileRead): void
}

export function ProfileList({ profiles, regeneratingId, launchingIds, launchErrors, ...actions }: ProfileListProps) {
  return <ul aria-label="浏览器配置列表" className="m-0 grid list-none grid-cols-1 items-stretch gap-5 p-0 md:grid-cols-2">
    {profiles.map((profile) => <ProfileCard key={profile.id} profile={profile} regenerating={regeneratingId === profile.id} regenerationDisabled={Boolean(regeneratingId)} launching={launchingIds?.has(profile.id)} launchError={launchErrors?.[profile.id]} {...actions} />)}
  </ul>
}
