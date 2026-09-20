import { useState } from 'react'
import type { NodeData } from '../../editor-store'
import { Label } from '../controls/label'
import { VariableInput } from '../controls/variable-input'

export function ProjectLifecycleConfig({ data, onChange }: { data: NodeData; onChange(key: string, value: unknown): void }) {
  const manual = data.moduleType === 'project_manual'
  const retain = (data.retainEnvironment ?? { enabled: false }) as Record<string, unknown>
  const [targets, setTargets] = useState(JSON.stringify(retain.recordTargets ?? [], null, 2))
  const [error, setError] = useState('')
  if (manual) return <div className="space-y-4">
    <p className="text-sm text-muted-foreground">暂停后，在项目的人工处理列表中继续或终结。继续不会重跑前面的节点。</p>
    <Label htmlFor="manual-reason">处理说明</Label>
    <VariableInput id="manual-reason" value={String(data.reason ?? '')} onChange={value => onChange('reason', value)} />
    <Label htmlFor="manual-deadline">等待上限（秒）</Label>
    <input id="manual-deadline" type="number" min={1} max={86400} value={Number(data.timeoutSeconds ?? 1800)} onChange={event => onChange('timeoutSeconds', Number(event.target.value))} />
  </div>
  const update = (key: string, value: unknown) => onChange('retainEnvironment', { ...retain, [key]: value })
  return <div className="space-y-4">
    <p className="text-sm text-muted-foreground">所有执行分支汇合后结束。浏览器关闭、环境保存及记录关联确认完成后，任务才会成功。</p>
    <label className="flex gap-2"><input type="checkbox" checked={retain.enabled === true} onChange={event => update('enabled', event.target.checked)} />保留当前环境</label>
    {retain.enabled === true && <>
      <Label htmlFor="end-mode">保存方式</Label>
      <select id="end-mode" value={String(retain.mode ?? 'saveAs')} onChange={event => update('mode', event.target.value)}><option value="saveAs">另存为新环境</option><option value="update">覆盖来源环境</option></select>
      {retain.mode === 'update' ? <>
        <Label htmlFor="end-generation">来源内容版本</Label>
        <VariableInput id="end-generation" value={String(retain.expectedContentGeneration ?? '')} onChange={value => update('expectedContentGeneration', value)} />
      </> : <>
        <Label htmlFor="end-name">环境名称（1–36 字，批量任务应使用不同名称）</Label>
        <VariableInput id="end-name" value={String(retain.name ?? '')} onChange={value => update('name', value)} placeholder="例如 {saved['ref']['recordKey']['value']}" />
      </>}
      <Label htmlFor="end-targets">关联记录（JSON 数组，支持变量）</Label>
      <textarea id="end-targets" className="min-h-32 w-full font-mono text-xs" value={targets} aria-invalid={Boolean(error)} onChange={event => setTargets(event.target.value)} onBlur={() => {
        try {
          const value: unknown = JSON.parse(targets)
          if (!Array.isArray(value)) throw new Error('array')
          update('recordTargets', value); onChange('retentionValid', true); setError('')
        } catch { onChange('retentionValid', false); setError('请输入 JSON 数组，每项包含 recordRef、expectedLinkRevision 和 replaceAllowed。') }
      }} />
      <p className="text-xs text-muted-foreground">仅能关联本任务已领取或创建的记录。关联失败时保留可修复结果。</p>
      {error && <p role="alert">{error}</p>}
    </>}
  </div>
}
