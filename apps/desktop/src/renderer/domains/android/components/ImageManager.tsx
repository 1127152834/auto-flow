import { useQuery } from '@tanstack/react-query'
import type { AndroidManagementApi } from '../management-api'

export function ImageManager({ api }: { api: Pick<AndroidManagementApi, 'images'> }) {
  const images = useQuery({ queryKey: ['android-management', 'images'], queryFn: api.images })
  if (images.isPending) return <section role="status">正在读取镜像目录…</section>
  if (images.isError || !images.data) return <section role="alert">镜像目录暂不可用。</section>
  const page = Array.isArray(images.data) ? { items: [] } : images.data
  return <section aria-label="镜像管理" className="rounded-card border border-line bg-surface p-5"><h2 className="font-semibold">镜像管理</h2><div className="mt-3 grid gap-2">{page.items.map(image => <article key={image.id} className="rounded-control border border-line p-3"><strong>{image.name}</strong><p className="text-xs text-muted">{image.imageId} · {image.state} · 验证 {String(image.verification?.state ?? 'not_tested')}</p></article>)}</div>{!page.items.length && <p className="mt-3 text-sm text-muted">尚未登记镜像。</p>}</section>
}
