import type { components } from '../../../shared/api/generated'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'

type EnvironmentPolicy = components['schemas']['AutomationWrite']['environmentPolicy']
export type ProxySelection = { mode: 'sourceDefault' | 'none' } | { mode: 'fixed'; proxyId: string } | { mode: 'pool'; proxyPoolId: string }
type Named = { id: string; name: string }
type Profile = Named & { browserVersion: string; browserEdition: string; proxyMode: 'none' | 'proxy' | 'pool'; proxyId?: string | null; proxyPoolId?: string | null }
export type AutomationResourceSummaryProps = {
  policy: EnvironmentPolicy
  projectDefaults: { profileId: string | null; proxy: ProxySelection; modelProviderId: string | null }
  profiles: Profile[]
  proxies: Named[]
  pools: Named[]
  models: Named[]
}
type Result = { value: string; source: string; status: '已选择' | '未配置' | '引用不可用' }
const selected = (id: string | null, items: Named[], source: string): Result => id === null ? { value: '未配置', source, status: '未配置' } : items.find(item => item.id === id) ? { value: items.find(item => item.id === id)!.name, source, status: '已选择' } : { value: '引用不可用', source, status: '引用不可用' }

export function AutomationResourceSummary({ policy, projectDefaults, profiles, proxies, pools, models }: AutomationResourceSummaryProps) {
  if (policy.source !== 'newFromProfile') return <Summary rows={['浏览器配置', 'CloakBrowser 内核', '代理', '模型'].map(item => [item, { value: '已保存的环境策略', source: '自动化配置', status: '已选择' }] as const)}/>
  const ownsProfile = Boolean(policy.profileId)
  const profileId = ownsProfile ? policy.profileId ?? null : projectDefaults.profileId
  const profileSource = ownsProfile ? '自动化配置' : '项目默认'
  const profile = profileId ? profiles.find(item => item.id === profileId) : undefined
  const browser = selected(profileId, profiles, profileSource)
  const kernel: Result = profile ? { value: `${profile.browserEdition === 'licensed' ? '正式版' : '公开版'} · ${profile.browserVersion}`, source: '浏览器配置', status: '已选择' } : { value: browser.value, source: '浏览器配置', status: browser.status }
  const proxySelection = policy.proxyOverride ?? projectDefaults.proxy
  const proxySource = policy.proxyOverride ? '自动化配置' : '项目默认'
  const proxy = (() => {
    if (proxySelection.mode === 'none') return { value: '不使用代理', source: proxySource, status: '已选择' } as Result
    if (proxySelection.mode === 'fixed') return selected(proxySelection.proxyId, proxies, proxySource)
    if (proxySelection.mode === 'pool') return selected(proxySelection.proxyPoolId, pools, proxySource)
    if (!profile) return { value: browser.value, source: '浏览器配置', status: browser.status } as Result
    if (profile.proxyMode === 'none') return { value: '不使用代理', source: '浏览器配置', status: '已选择' } as Result
    return profile.proxyMode === 'proxy' ? selected(profile.proxyId ?? null, proxies, '浏览器配置') : selected(profile.proxyPoolId ?? null, pools, '浏览器配置')
  })()
  const ownsModel = Object.hasOwn(policy, 'modelProviderId')
  const model = selected(ownsModel ? policy.modelProviderId ?? null : projectDefaults.modelProviderId, models, ownsModel ? '自动化配置' : '项目默认')
  return <Summary rows={[['浏览器配置', browser], ['CloakBrowser 内核', kernel], ['代理', proxy], ['模型', model]]}/>
}

function Summary({ rows }: { rows: readonly (readonly [string, Result])[] }) {
  return <section className="grid min-w-0 gap-2 border-t border-line pt-3 md:grid-cols-[12rem_minmax(0,1fr)]" aria-label="资源检查"><h4 className="m-0 pt-2 text-sm font-semibold">资源检查</h4><TableScroll label="资源检查表" className="min-w-0 rounded-control border border-line"><Table className="min-w-[640px]"><TableHeader><TableRow><TableHead>项目</TableHead><TableHead>最终采用</TableHead><TableHead>来源</TableHead><TableHead>状态</TableHead></TableRow></TableHeader><TableBody>{rows.map(([name, result]) => <TableRow key={name}><TableCell className="font-medium">{name}</TableCell><TableCell className="max-w-64 truncate" title={result.value}>{result.value}</TableCell><TableCell>{result.source}</TableCell><TableCell>{result.status}</TableCell></TableRow>)}</TableBody></Table></TableScroll></section>
}
