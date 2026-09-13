import { Button } from '../../../shared/components/ui/button'
import type { ProjectTab } from '../types'

const tabs: Array<{ value: ProjectTab; label: string }> = [{ value: 'overview', label: '概览' }, { value: 'automations', label: '自动化' }, { value: 'runs', label: '运行记录' }, { value: 'statistics', label: '统计' }, { value: 'data', label: '数据' }, { value: 'environments', label: '环境' }]
export function ProjectTabs({ value, onChange }: { value: ProjectTab; onChange(value: ProjectTab): void }) {
  return <nav aria-label="项目功能" className="flex gap-6 overflow-x-auto border-b border-line">{tabs.map(tab => <Button key={tab.value} variant="ghost" aria-current={value === tab.value ? 'page' : undefined} className={`rounded-none border-x-0 border-t-0 h-auto min-h-14 px-4 py-4 text-base font-medium ${value === tab.value ? 'border-b-2 border-clay text-ink' : 'border-b-2 border-transparent text-muted'}`} onClick={() => onChange(tab.value)}>{tab.label}</Button>)}</nav>
}
