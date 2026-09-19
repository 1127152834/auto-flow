import { ApiClientError } from '../api/client'

/**
 * The owners the service refuses to break, exactly as it reported them.
 *
 * ``RESOURCE_REFERENCED`` is the only 409 that carries this list; every other
 * failure keeps its own message. There is no force flag, so the list is the
 * user's whole recovery path.
 */
export type ResourceReference = {
  kind?: string
  projectId?: string
  projectName?: string
  automationId?: string
  automationName?: string
  profileId?: string
  profileName?: string
  path?: string[]
}

export function resourceReferences(error: unknown): ResourceReference[] {
  if (!(error instanceof ApiClientError) || error.code !== 'RESOURCE_REFERENCED') return []
  const value = error.details.references
  if (!Array.isArray(value)) return []
  return value.filter((item): item is ResourceReference => typeof item === 'object' && item !== null)
}

function describe(reference: ResourceReference): string {
  if (reference.automationName) return `${reference.projectName ?? reference.projectId ?? ''} · 自动化「${reference.automationName}」`
  if (reference.profileName) return `${reference.projectName ?? reference.projectId ?? ''} · 浏览器配置「${reference.profileName}」`
  return reference.projectName ?? reference.projectId ?? reference.kind ?? '未知对象'
}

export function ResourceReferenceList({ error }: { error: unknown }) {
  const references = resourceReferences(error)
  if (!references.length) return null
  return <div role="alert" className="grid gap-1 rounded-control border border-clay/30 bg-clay/10 px-3 py-2 text-sm">
    <p className="m-0 font-medium text-ink">仍被以下对象引用，删除会破坏它们下次运行：</p>
    <ul className="m-0 grid list-none gap-1 p-0 text-muted">
      {references.map((reference, index) => <li key={`${reference.kind ?? 'ref'}-${index}`} className="break-all">
        {describe(reference)}
        {reference.path?.length ? <span className="text-xs text-muted">（{reference.path.join('.')}）</span> : null}
      </li>)}
    </ul>
    <p className="m-0 text-xs text-muted">请先在对应项目或自动化里改用别的资源，再回来删除。</p>
  </div>
}
