import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import type { FleetApi, Profile } from '../fleet-api'
import type { Image } from '../management-api'

const empty = (): Profile => ({ id: crypto.randomUUID(), revision: 0, name: '', imageId: '', width: 720, height: 1280, dpi: 320, cpu: 1, memoryMb: 1536, locale: 'zh-CN', timezone: 'Asia/Shanghai', shellRoot: 'unknown', applicationRoot: 'unknown', archived: false })

type TemplateApi = Pick<FleetApi, 'profiles' | 'standardProfile' | 'saveProfile'> & { archiveProfile: (id: string, body: { requestId: string; expectedRevision: number }) => Promise<Profile>; images: () => Promise<{ items: Image[]; total: number; nextCursor: string | null }> }

export function TemplateManager({ api }: { api: TemplateApi }) {
  const profiles = useQuery({ queryKey: ['android', 'profiles'], queryFn: api.profiles })
  const images = useQuery({ queryKey: ['android-management', 'images'], queryFn: api.images })
  const [draft, setDraft] = useState<Profile | null>(null), [archive, setArchive] = useState<Profile | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const active = (profiles.data ?? []).filter(profile => !profile.archived)
  const imageItems = Array.isArray(images.data) ? images.data : images.data?.items ?? []
  const verifiedImage = imageItems.find(image => image.imageId === draft?.imageId && image.state === 'verified' && image.verification?.state === 'passed')
  const imageValid = Boolean(draft?.imageId.trim() && verifiedImage)
  const update = <K extends keyof Profile>(key: K, value: Profile[K]) => setDraft(current => current ? { ...current, [key]: value } : current)
  const save = async () => {
    if (!draft) return
    if (!draft.name.trim() || !imageValid) { setError('镜像必须来自已验证目录，且模板名称不能为空'); return }
    setBusy(true); setError('')
    try { await api.saveProfile(draft); setDraft(null); await profiles.refetch() }
    catch (cause) { setError(cause instanceof ApiClientError && cause.status === 409 ? '模板已更新，请重新加载后编辑' : cause instanceof Error ? cause.message : '模板保存失败') }
    finally { setBusy(false) }
  }
  const reload = async () => { setError(''); const refreshed = await profiles.refetch(); const current = (refreshed.data ?? []).find(item => item.id === draft?.id); if (current) setDraft({ ...current }) }
  const confirmArchive = async () => {
    if (!archive) return
    setBusy(true); setError('')
    try { await api.archiveProfile(archive.id, { requestId: crypto.randomUUID(), expectedRevision: archive.revision }); setArchive(null); await profiles.refetch() }
    catch (cause) { setError(cause instanceof Error ? cause.message : '模板归档失败') }
    finally { setBusy(false) }
  }
  if (draft) return <section aria-label="设备模板" className="rounded-card border border-line bg-surface p-5"><h2 className="font-semibold">{draft.revision ? '编辑设备模板' : '新建设备模板'}</h2><div className="mt-3 grid gap-3"><label>模板名称<input aria-label="模板名称" value={draft.name} onChange={event => update('name', event.target.value)} disabled={busy || Boolean(error && error.includes('重新加载'))} /></label><label>固定镜像 ID<input aria-label="固定镜像 ID" value={draft.imageId} onChange={event => update('imageId', event.target.value)} disabled={busy || Boolean(error && error.includes('重新加载'))} /></label>{draft.imageId && !verifiedImage && <p role="status" className="text-sm text-danger">镜像必须来自已验证目录，当前镜像尚未验证通过。</p>}{([['width', '宽度'], ['height', '高度'], ['dpi', '显示密度'], ['cpu', 'CPU 核数'], ['memoryMb', '内存 MB']] as const).map(([key, label]) => <label key={key}>{label}<input aria-label={label} type="number" value={draft[key]} onChange={event => update(key, Number(event.target.value))} disabled={busy || Boolean(error && error.includes('重新加载'))} /></label>)}<label>语言<select value={draft.locale} onChange={event => update('locale', event.target.value)} disabled={busy}><option value="zh-CN">简体中文</option><option value="en-US">English</option></select></label><label>时区<input aria-label="时区" value={draft.timezone} onChange={event => update('timezone', event.target.value)} disabled={busy} /></label></div>{error && <p role="alert" className="mt-3 text-sm">{error}</p>}<div className="mt-4 flex gap-2"><button type="button" disabled={busy || !draft.name.trim() || !imageValid || Boolean(error && error.includes('重新加载'))} onClick={() => void save()}>保存模板</button>{error.includes('重新加载') && <button type="button" disabled={busy} onClick={() => void reload()}>重新加载模板</button>}<button type="button" disabled={busy} onClick={() => setDraft(null)}>取消</button></div></section>
  return <section aria-label="设备模板" className="rounded-card border border-line bg-surface p-5"><header className="flex items-center justify-between gap-3"><div><h2 className="font-semibold">设备模板</h2><p className="mt-1 text-sm text-muted">模板只保存创建默认值；已创建实例使用自己的配置快照。</p></div><button type="button" onClick={() => { setError(''); setDraft(empty()) }}>新建模板</button></header><div className="mt-3 grid gap-2">{active.map(profile => <article key={profile.id} className="rounded-control border border-line p-3"><div className="flex items-start justify-between gap-3"><strong>{profile.name}</strong><span className="text-xs text-muted">修订 {profile.revision}</span></div><p className="text-xs text-muted">镜像 {profile.imageId} · {profile.width} × {profile.height} · {profile.memoryMb} MB</p><div className="mt-2 flex flex-wrap gap-2"><button type="button" aria-label={`编辑${profile.name}`} onClick={() => { setError(''); setDraft({ ...profile }) }}>编辑</button><button type="button" aria-label={`复制${profile.name}`} onClick={() => { setError(''); setDraft({ ...profile, id: crypto.randomUUID(), name: `${profile.name} 副本`, revision: 0, archived: false }) }}>复制</button><button type="button" aria-label={`归档${profile.name}`} onClick={() => setArchive(profile)}>归档</button></div></article>)}</div>{!active.length && <p className="mt-3 text-sm text-muted">尚未创建模板。</p>}{!active.length && <button type="button" disabled={!imageItems.some(image => image.state === 'verified' && image.verification?.state === 'passed')} onClick={() => void api.standardProfile().then(() => profiles.refetch())}>创建标准模板</button>}{archive && <div role="dialog" aria-label="归档模板确认" className="mt-4 rounded-control border border-line bg-surface-subtle p-3"><p>归档后不能用于新建实例，已创建实例的配置保持不变。</p><div className="mt-2 flex gap-2"><button type="button" disabled={busy} onClick={() => void confirmArchive()}>确认归档</button><button type="button" disabled={busy} onClick={() => setArchive(null)}>取消</button></div></div>}{error && <p role="alert" className="mt-3 text-sm">{error}</p>}</section>
}
