import { Button } from '../shared/components/ui/button'
import { GearSix } from '@phosphor-icons/react'

export type AppRoute = 'dashboard' | 'profiles' | 'proxies' | 'models' | 'settings'
const tabs: { key: AppRoute; label: string }[] = [{ key: 'dashboard', label: '总览' }, { key: 'profiles', label: '浏览器配置' }, { key: 'proxies', label: '代理管理' }, { key: 'models', label: '模型管理' }]
export function routeFromHash(): AppRoute {
  const route = window.location.hash.replace(/^#\/?/, '').split('?')[0]
  return [...tabs.map(tab => tab.key), 'settings'].includes(route) ? route as AppRoute : 'dashboard'
}
export function ApplicationHeader({ route, onNavigate, status }: { route: AppRoute; onNavigate(route: AppRoute): void; status: 'loading' | 'connected' | 'offline' }) {
  return <header className="flex min-h-[74px] flex-wrap items-center gap-x-8 gap-y-2 border-b border-line bg-surface px-5 py-2 md:px-8">
    <a href="#/dashboard" className="flex items-center gap-3 text-xl font-semibold text-ink no-underline"><img src="./brand/autoflow-mark.png" width="34" height="34" alt="" />AutoFlow</a>
    <nav aria-label="全局导航" className="flex min-h-14 items-stretch gap-5">{tabs.map(tab => <Button variant="ghost" type="button" key={tab.key} aria-current={route === tab.key ? 'page' : undefined} onClick={() => onNavigate(tab.key)} className={`h-auto rounded-none border-0 border-b-2 bg-transparent px-1 text-sm font-semibold ${route === tab.key ? 'border-clay text-clay' : 'border-transparent text-muted hover:text-ink'}`}>{tab.label}</Button>)}</nav>
    <div className="ml-auto flex min-h-14 items-center gap-5"><Button variant="ghost" type="button" aria-current={route === 'settings' ? 'page' : undefined} onClick={() => onNavigate('settings')} className={`h-auto rounded-none flex min-h-14 items-center gap-2 border-0 border-b-2 bg-transparent text-sm font-semibold ${route === 'settings' ? 'border-clay text-clay' : 'border-transparent text-muted'}`}><GearSix size={21} />设置</Button><span className="h-5 w-px bg-line" /><span role="status" className="flex items-center gap-2 text-xs text-muted"><span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${status === 'connected' ? 'bg-sage' : status === 'loading' ? 'bg-warning' : 'bg-danger'}`} />{status === 'connected' ? '本地服务正常' : status === 'loading' ? '本地服务连接中' : '本地服务未连接'}</span></div>
  </header>
}
