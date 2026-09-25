import type { NodeData } from '../../editor-store'
import { Label } from '../controls/label'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { SelectNative } from '../controls/select-native'

export function DiagnosticConfig({ data, onChange }: { data: NodeData; onChange(key: string, value: unknown): void }) {
  return <div className="space-y-3">
    <Label htmlFor="diagnostic-name">诊断名称</Label>
    <VariableInput id="diagnostic-name" value={String(data.diagnosticName ?? '')} onChange={value => onChange('diagnosticName', value)} />
    {data.moduleType === 'trace_mark' && <>
      <Label htmlFor="diagnostic-description">说明</Label>
      <VariableInput id="diagnostic-description" value={String(data.description ?? '')} onChange={value => onChange('description', value)} />
      <Label htmlFor="diagnostic-correlation">业务关联值</Label>
      <VariableInput id="diagnostic-correlation" value={String(data.correlation ?? '')} onChange={value => onChange('correlation', value)} />
      <p className="text-xs text-muted-foreground">每次执行产生独立标记 ID；已识别的敏感变量值会隐藏。未启动浏览器时只写入运行日志。</p>
    </>}
    {data.moduleType === 'capture_diagnostics' && <>
      <Label htmlFor="diagnostic-target">DOM 采集范围</Label>
      <SelectNative id="diagnostic-target" value={String(data.target ?? 'page')} onChange={event => onChange('target', event.target.value)}>
        <option value="page">当前标签页</option><option value="frame">当前选中的 iframe</option>
      </SelectNative>
      {Object.entries({ includeScreenshot: '标签页视口截图', includeDom: '只读 DOM 文档', includeConsole: '最近 100 条控制台证据引用' }).map(([key, label]) => <label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={data[key] !== false} onChange={event => onChange(key, event.target.checked)} />{label}</label>)}
      <p className="text-xs text-muted-foreground">先用现有切换 iframe 节点选择框架；截图始终为标签页视口。输出仅包含产物引用和缺失说明，不执行页面内容。</p>
    </>}
    {data.moduleType === 'save_trace_segment' && <>
      <Label htmlFor="diagnostic-marker">起始标记 ID（可选）</Label>
      <VariableInput id="diagnostic-marker" value={String(data.startMarker ?? '')} onChange={value => onChange('startMarker', value)} placeholder="{trace_marker[id]}" />
      <p className="text-xs text-muted-foreground">为空时从采集起点开始。保存结构化事件与产物引用 JSON；不关闭采集，也不生成尚未归档的原生 ZIP。重复标记名称不会隐式选择某一轮。</p>
    </>}
    <Label htmlFor="diagnostic-output">输出变量</Label>
    <VariableNameInput id="diagnostic-output" value={String(data.variableName ?? '')} onChange={value => onChange('variableName', value)} />
  </div>
}
