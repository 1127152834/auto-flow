import type { ProjectTab } from '../types'
const labels: Record<Exclude<ProjectTab, 'overview'>, string> = { automations: '自动化', runs: '运行记录', statistics: '统计', data: '数据', environments: '环境' }
export function ProjectCapabilityState({ tab }: { tab: Exclude<ProjectTab, 'overview'> }) {
  return <section role="status" className="rounded-card border border-line bg-surface px-6 py-16 text-center"><h2 className="m-0 text-lg font-semibold text-ink">{labels[tab]}暂未开放</h2><p className="mb-0 mt-2 text-sm text-muted">后续版本会在这里接入真实项目能力。</p></section>
}
