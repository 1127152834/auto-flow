import { useId } from 'react'
import { getStudioOpenContext } from '../../api/config'
import type { NodeData } from '../../editor-store'
import { useProjectInputs } from '../../project-inputs'
import { useSignatureStore } from '../../hooks/stores/signatureStore'
import { Label } from '../controls/label'
import { SelectNative } from '../controls/select-native'
import { VariableInput } from '../controls/variable-input'

export function ProjectEndConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  const id = useId()
  const retain = data.retainEnvironment === true
  const automation = useProjectInputs(state => state.automation)
  const groups = useSignatureStore(state => state.inputs)
  const options = (automation?.inputPlan.inputs ?? []).map(input => ({ inputId: input.inputId, label: groups.find(group => group.key === input.signatureInput)?.name ?? input.alias ?? '未命名输入' }))
  const linkAll = !Array.isArray(data.inputIds)
  const linked = Array.isArray(data.inputIds) ? data.inputIds as string[] : options.map(option => option.inputId)
  const result = data.businessResult === 'failed' ? 'failed' : data.businessResult === undefined || data.businessResult === 'succeeded' ? 'succeeded' : 'variable'
  const staticTargets = Array.isArray(data.recordTargets) && data.recordTargets.length > 0 ? data.recordTargets : null
  return <div className="space-y-4">
    <p className="text-xs text-muted-foreground">结束当前项目任务。保存与记录关联全部确认后才报告成功；不会执行后续节点。</p>
    {!getStudioOpenContext().projectId && <p role="alert">请从项目打开工作流；项目 End 需要正式任务授权。</p>}
    <div className="space-y-2"><Label htmlFor={`${id}-result`}>业务结果</Label>
      <SelectNative id={`${id}-result`} value={result} onChange={event => onChange('businessResult', event.target.value === 'variable' ? '' : event.target.value)}>
        <option value="succeeded">成功</option><option value="failed">失败</option><option value="variable">按变量</option>
      </SelectNative>
      {result === 'variable' && <VariableInput aria-label="结果变量" value={typeof data.businessResult === 'string' ? data.businessResult : ''} onChange={value => onChange('businessResult', value)} placeholder="例如 {login_result}，内容需为 succeeded 或 failed" />}</div>
    <label className="flex gap-2"><input type="checkbox" checked={retain} onChange={event => onChange('retainEnvironment', event.target.checked)} />保留当前身份的登录状态</label>
    <p className="text-xs text-muted-foreground">保存后，下次可直接用这个身份继续，不必重新登录。试跑（仅预览）时保留登录状态会被拒绝，请在真实运行中使用。</p>
    {retain && <>
      <div className="space-y-2"><Label htmlFor={`${id}-mode`}>保存方式</Label>
        <SelectNative id={`${id}-mode`} value={String(data.saveMode ?? 'auto')} onChange={event => onChange('saveMode', event.target.value)}>
          <option value="auto">更新当前来源；新环境则另存</option><option value="save_as">另存为新环境</option>
        </SelectNative></div>
      <div className="space-y-2"><Label htmlFor={`${id}-name`}>新环境名称</Label>
        <input id={`${id}-name`} className="w-full rounded border bg-background px-2 py-1" value={String(data.name ?? '保留环境')} maxLength={36} onChange={event => onChange('name', event.target.value)} /></div>
      <fieldset className="space-y-1"><legend className="text-sm">关联到</legend>
        {options.length === 0 ? <p className="text-xs text-muted-foreground">当前流程还没有可关联的输入。</p> : <>
          <label className="flex gap-2"><input type="checkbox" checked={linkAll} onChange={event => onChange('inputIds', event.target.checked ? null : [])} />全部可写输入</label>
          {options.map(option => <label className="flex gap-2" key={option.inputId}>
            <input type="checkbox" checked={linked.includes(option.inputId)} onChange={event => onChange('inputIds', event.target.checked ? [...linked, option.inputId] : linked.filter(item => item !== option.inputId))} />{option.label}
          </label>)}
        </>}
        <p className="text-xs text-muted-foreground">勾选的输入会记下这次保存的登录状态；都不勾选则只保存、不关联。纯查询的输入不能关联。</p></fieldset>
      <div className="space-y-2"><Label htmlFor={`${id}-targets`}>新增或已写记录的数据行列表</Label>
        {staticTargets ? <>
          <textarea id={`${id}-targets`} aria-label="静态记录目标" className="w-full rounded border bg-muted px-2 py-1 font-mono text-xs" rows={4} readOnly value={JSON.stringify(staticTargets, null, 2)} />
          <button type="button" className="text-xs text-destructive underline" onClick={() => onChange('recordTargets', [])}>清空记录目标</button>
        </> : <VariableInput id={`${id}-targets`} value={typeof data.recordTargets === 'string' ? data.recordTargets : ''} onChange={value => onChange('recordTargets', value || [])} placeholder="例如 {created_records}；留空不追加记录" />}</div>
      <label className="flex gap-2"><input type="checkbox" checked={data.replaceAllowed === true} onChange={event => onChange('replaceAllowed', event.target.checked)} />允许替换所选记录已有的环境关联</label>
      <p className="text-xs text-muted-foreground">仅接受当前任务仍持有写入占用的记录，关联版本冲突会保留已保存环境并报告失败。零目标时只保存环境，不关联记录。</p>
    </>}
  </div>
}
