import { useQuery } from '@tanstack/react-query'
import type { FleetApi } from '../fleet-api'

export function TemplateManager({ api }: { api: Pick<FleetApi, 'profiles' | 'standardProfile'> }) {
  const profiles = useQuery({ queryKey: ['android', 'profiles'], queryFn: api.profiles })
  return <section aria-label="设备模板" className="rounded-card border border-line bg-surface p-5"><h2 className="font-semibold">设备模板</h2><div className="mt-3 grid gap-2">{(profiles.data ?? []).filter(profile => !profile.archived).map(profile => <article key={profile.id} className="rounded-control border border-line p-3"><strong>{profile.name}</strong><p className="text-xs text-muted">修订 {profile.revision} · {profile.width} × {profile.height} · {profile.memoryMb} MB</p></article>)}</div>{!profiles.data?.length && <button type="button" onClick={() => void api.standardProfile().then(() => profiles.refetch())}>创建标准模板</button>}</section>
}
