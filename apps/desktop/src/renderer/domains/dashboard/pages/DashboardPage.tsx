import type { ApiClient } from '../../../shared/api/client'
import { Button } from '../../../shared/components/ui/button'
import { ResourceOverview, WorkEntrances } from '../components/DashboardCards'
import { useDashboard } from '../hooks/useDashboard'

type Target = 'profiles' | 'proxies' | 'models' | 'settings'
export function DashboardPage({ client, onNavigate }: { client: ApiClient; onNavigate(target: Target): void }) {
  const query = useDashboard(client)
  return <main className="min-h-dvh bg-canvas px-4 py-8 text-ink sm:px-6 lg:px-8"><div className="mx-auto grid w-full max-w-[1180px] gap-8"><header><h1 className="m-0 text-3xl font-semibold">总览</h1><p className="mb-0 mt-2 text-muted">集中查看本机资源，并进入日常管理工作。</p></header>{query.isPending ? <div className="grid animate-pulse gap-4" role="status" aria-label="正在加载资源概况"><div className="grid gap-4 sm:grid-cols-3">{[1,2,3].map(i => <div key={i} className="h-40 rounded-card bg-surface-subtle" />)}</div><span className="sr-only">正在加载…</span></div> : query.isError ? <section role="alert" className="rounded-card border border-red-200 bg-red-50 p-6"><h2 className="m-0 text-lg">资源概况加载失败</h2><p className="text-sm text-red-800">{query.error.message}</p><Button onClick={() => void query.refetch()}>重试</Button></section> : query.data ? <ResourceOverview data={query.data} /> : <section className="rounded-card border border-line bg-surface p-8 text-center"><h2>还没有资源</h2><p className="text-muted">从浏览器配置、代理或模型开始。</p></section>}<WorkEntrances onNavigate={onNavigate} /></div></main>
}
