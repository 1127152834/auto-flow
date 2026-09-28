import { useId } from 'react'
import { getStudioOpenContext } from '../../api/config'
import type { NodeData } from '../../editor-store'
import { Label } from '../controls/label'
import { SelectNative } from '../controls/select-native'
import { VariableInput } from '../controls/variable-input'

export function ProjectEndConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  const id = useId()
  const retain = data.retainEnvironment === true
  return <div className="space-y-4">
    <p className="text-xs text-muted-foreground">结束当前项目任务。保存与记录关联全部确认后才报告成功；不会执行后续节点。</p>
    {!getStudioOpenContext().projectId && <p role="alert">请从项目打开工作流；项目 End 需要正式任务授权。</p>}
    <div className="space-y-2"><Label htmlFor={`${id}-result`}>业务结果</Label>
      <SelectNative id={`${id}-result`} value={String(data.businessResult ?? 'succeeded')} onChange={event => onChange('businessResult', event.target.value)}>
        <option value="succeeded">成功</option><option value="failed">失败</option>
      </SelectNative></div>
    <label className="flex gap-2"><input type="checkbox" checked={retain} onChange={event => onChange('retainEnvironment', event.target.checked)} />保留当前环境并关联记录</label>
    {retain && <>
      <div className="space-y-2"><Label htmlFor={`${id}-mode`}>保存方式</Label>
        <SelectNative id={`${id}-mode`} value={String(data.saveMode ?? 'auto')} onChange={event => onChange('saveMode', event.target.value)}>
          <option value="auto">更新当前来源；新环境则另存</option><option value="save_as">另存为新环境</option>
        </SelectNative></div>
      <div className="space-y-2"><Label htmlFor={`${id}-name`}>新环境名称</Label>
        <input id={`${id}-name`} className="w-full rounded border bg-background px-2 py-1" value={String(data.name ?? '保留环境')} maxLength={36} onChange={event => onChange('name', event.target.value)} /></div>
      <div className="space-y-2"><Label htmlFor={`${id}-inputs`}>关联输入标识（逗号分隔）</Label>
        <input id={`${id}-inputs`} className="w-full rounded border bg-background px-2 py-1" value={Array.isArray(data.inputIds) ? data.inputIds.join(',') : '*'} onChange={event => onChange('inputIds', event.target.value.trim() === '*' ? null : event.target.value.split(',').map(value => value.trim()).filter(Boolean))} />
        <p className="text-xs text-muted-foreground">* 表示本任务全部可写输入；清空表示不关联输入。纯查询记录不具备关联写权。</p></div>
      <div className="space-y-2"><Label htmlFor={`${id}-targets`}>新增或已写记录的 RecordRef 列表</Label>
        <VariableInput id={`${id}-targets`} value={typeof data.recordTargets === 'string' ? data.recordTargets : ''} onChange={value => onChange('recordTargets', value || [])} placeholder="例如 {created_records}；留空不追加记录" /></div>
      <label className="flex gap-2"><input type="checkbox" checked={data.replaceAllowed === true} onChange={event => onChange('replaceAllowed', event.target.checked)} />允许替换所选记录已有的环境关联</label>
      <p className="text-xs text-muted-foreground">仅接受当前任务仍持有写入占用的记录，关联版本冲突会保留已保存环境并报告失败。零目标时只保存环境，不关联记录。</p>
    </>}
  </div>
}
