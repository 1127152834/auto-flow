import { GearSix } from '@phosphor-icons/react'
import type { AppRoute } from './navigation'

const tabs: { key: AppRoute; label: string }[] = [{ key: 'dashboard', label: '总览' }, { key: 'projects', label: '项目' }, { key: 'profiles', label: '浏览器配置' }, { key: 'android', label: '安卓设备' }, { key: 'proxies', label: '代理管理' }, { key: 'models', label: '模型管理' }, { key: 'lab', label: '实验室' }]
export function ApplicationHeader({ route, onNavigate, status }: { route: AppRoute; onNavigate(route: AppRoute): void; status: 'loading' | 'connected' | 'offline' }) {
  return <header className="flex min-h-[74px] flex-wrap items-center gap-x-8 gap-y-2 border-b border-line bg-surface px-5 py-2 md:px-8">
    <a href="#/dashboard" onClick={event => { event.preventDefault(); onNavigate('dashboard') }} className="flex items-center gap-3 text-xl font-semibold text-ink no-underline"><img src="./brand/autoflow-mark.png" width="34" height="34" alt="" />AutoFlow</a>
    <nav aria-label="全局导航" className="flex min-h-14 max-w-full items-stretch gap-5 overflow-x-auto">{tabs.map(tab => <button type="button" key={tab.key} aria-current={route === tab.key ? 'page' : undefined} onClick={() => onNavigate(tab.key)} className={`shrink-0 whitespace-nowrap border-0 border-b-2 bg-transparent px-1 text-sm font-semibold ${route === tab.key ? 'border-clay text-clay' : 'border-transparent text-muted hover:text-ink'}`}>{tab.label}</button>)}</nav>
    <div className="ml-auto flex min-h-14 items-center gap-5"><button type="button" aria-current={route === 'settings' ? 'page' : undefined} onClick={() => onNavigate('settings')} className={`flex min-h-14 items-center gap-2 border-0 border-b-2 bg-transparent text-sm font-semibold ${route === 'settings' ? 'border-clay text-clay' : 'border-transparent text-muted'}`}><GearSix size={21} />设置</button><span className="h-5 w-px bg-line" /><span role="status" className="flex items-center gap-2 text-xs text-muted"><span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${status === 'connected' ? 'bg-sage' : status === 'loading' ? 'bg-amber-500' : 'bg-red-600'}`} />{status === 'connected' ? '本地服务正常' : status === 'loading' ? '本地服务连接中' : '本地服务未连接'}</span></div>
  </header>
}
