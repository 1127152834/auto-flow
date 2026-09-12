import { ArrowRight, Browser, Cube, FlowArrow, GearSix, Globe, Stack } from '@phosphor-icons/react'
import type { DashboardSnapshot } from '../api'

const resourceCards = [
  { key: 'profiles', label: '浏览器配置', caption: '个全局配置模板', icon: Browser },
  { key: 'enabledProxies', label: '已启用代理', caption: '个代理出口已启用', icon: Globe },
  { key: 'proxyGroups', label: '代理组', caption: '个本地代理组', icon: Stack },
  { key: 'installedKernels', label: '已安装内核', caption: '个浏览器内核', icon: Browser },
  { key: 'modelProviders', label: '模型供应商', caption: '个供应商', icon: Cube },
  { key: 'models', label: '模型', caption: '个已配置模型', icon: Cube },
] as const

export function ResourceOverview({ data }: { data: DashboardSnapshot }) {
  const empty = data.profiles + data.enabledProxies + data.proxyGroups + data.installedKernels + (data.modelProviders ?? 0) + (data.models ?? 0) === 0
  return <section aria-labelledby="resources-heading"><h2 id="resources-heading" className="mb-4 text-xl font-semibold">资源概况</h2>{empty ? <p className="mb-4 rounded-control border border-line bg-surface px-4 py-3 text-sm text-muted">还没有已配置的资源，可从下方工作入口开始。</p> : null}<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{resourceCards.map(({ key, label, caption, icon: Icon }) => <article key={key} className="rounded-card border border-line bg-surface p-5 shadow-[0_7px_22px_rgba(69,62,52,0.05)]"><span className="grid h-11 w-11 place-items-center rounded-control bg-clay-soft text-clay"><Icon size={23} weight="duotone" /></span><span className="mt-4 block text-sm text-muted">{label}</span>{data[key] == null ? <strong className="mt-2 block text-lg">未接入</strong> : <><strong className="mt-1 block text-3xl">{data[key]}</strong><small className="text-muted">{caption}</small></>}</article>)}</div></section>
}

const links = [
  { target: 'automationStudio', title: '工作流工作台', hint: '在独立窗口中打开工作流编排工作台', icon: FlowArrow },
  { target: 'profiles', title: '管理浏览器配置', hint: '维护浏览器身份、内核与代理绑定', icon: Browser },
  { target: 'proxies', title: '管理代理出口', hint: '维护代理连接与本地代理组', icon: Globe },
  { target: 'models', title: '管理模型资源', hint: '连接供应商并维护模型目录', icon: Cube },
  { target: 'settings', title: '查看本地设置', hint: '管理工作区、应用偏好与诊断', icon: GearSix },
] as const

export type WorkEntranceTarget = typeof links[number]['target']

export function WorkEntrances({ onNavigate }: { onNavigate(target: WorkEntranceTarget): void }) {
  return <section aria-labelledby="work-heading"><h2 id="work-heading" className="mb-4 text-xl font-semibold">工作入口</h2><div className="grid gap-3 sm:grid-cols-2">{links.map(({ target, title, hint, icon: Icon }) => <button key={target} type="button" onClick={() => onNavigate(target)} className="flex items-center gap-4 rounded-card border border-line bg-surface p-5 text-left shadow-[0_7px_22px_rgba(69,62,52,0.04)] transition hover:-translate-y-px hover:border-clay focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-clay"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-control bg-surface-subtle text-clay"><Icon size={23} /></span><span className="min-w-0 flex-1"><strong className="block">{title}</strong><small className="mt-1 block text-muted">{hint}</small></span><ArrowRight className="shrink-0 text-muted" /></button>)}</div></section>
}
