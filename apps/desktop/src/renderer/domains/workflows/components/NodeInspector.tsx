import { useRef, useState } from 'react'
import { BracketsCurly, SlidersHorizontal } from '@phosphor-icons/react'
import { FormField } from '../../../shared/components/FormField'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Switch } from '../../../shared/components/ui/switch'
import { Textarea } from '../../../shared/components/ui/textarea'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../../../shared/components/ui/dropdown-menu'
import type { NodeDefinition, WorkflowIssue, WorkflowNode, WorkflowVariable } from '../types'

type Props = {
  selectorTools?: React.ReactNode
  controlFields?: React.ReactNode
  node: WorkflowNode | null
  definition?: NodeDefinition
  variables: WorkflowVariable[]
  issues: WorkflowIssue[]
  onChange(patch: Record<string, unknown>): void
  onLabelChange(label: string): void
  onEditStart?(): void
  onEditEnd?(): void
  disabled?: boolean
}

export function NodeInspector(props: Props) {
  if (!props.node) return <div className="flex h-full flex-col items-center justify-center gap-3 px-6 py-14 text-center text-muted">
    <SlidersHorizontal size={28} />
    <p className="text-sm font-medium">选择一个节点</p>
    <p className="text-xs leading-5">点击画布中的节点，在这里配置参数。</p>
  </div>
  return <NodeFields key={props.node.id} {...props} node={props.node} />
}

function NodeFields({ node, definition, variables, issues, selectorTools, controlFields, onChange, onLabelChange, onEditStart, onEditEnd, disabled = false }: Props & { node: WorkflowNode }) {
  const activeInput = useRef<{ field: string; input: HTMLInputElement | HTMLTextAreaElement; start: number; end: number } | null>(null)
  const [hasTarget, setHasTarget] = useState(false)
  const nodeIssues = issues.filter((issue) => issue.nodeId === node.id)
  const fieldError = (field: string) => nodeIssues.filter((issue) => issue.path.at(-1) === field).map((issue) => issue.message).join('；') || undefined
  const value = (field: string) => node.config[field] == null ? '' : String(node.config[field])
  const clearTextTarget = () => { activeInput.current = null; setHasTarget(false) }
  const bindTextTarget = (field: string, input: HTMLInputElement | HTMLTextAreaElement) => {
    activeInput.current = { field, input, start: input.selectionStart ?? input.value.length, end: input.selectionEnd ?? input.value.length }
    setHasTarget(true)
  }
  const text = (field: string, label: string, hint?: string, multiline = false, references = true) => {
    const props = {
      value: value(field), disabled,
      onFocus: (event: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        onEditStart?.()
        if (references) bindTextTarget(field, event.currentTarget)
        else clearTextTarget()
      },
      onBlur: onEditEnd,
      onSelect: (event: React.SyntheticEvent<HTMLInputElement | HTMLTextAreaElement>) => { if (references) bindTextTarget(field, event.currentTarget) },
      onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        onChange({ [field]: event.target.value })
        if (references) bindTextTarget(field, event.currentTarget)
      },
    }
    return <FormField key={field} htmlFor={`node-${node.id}-${field}`} label={label} hint={hint} error={fieldError(field)}>
      {multiline ? <Textarea {...props} /> : <Input {...props} />}
    </FormField>
  }
  const select = (field: string, label: string, options: [string, string][]) => <FormField key={field} htmlFor={`node-${node.id}-${field}`} label={label} error={fieldError(field)}>
    <Select className="w-full" value={value(field)} disabled={disabled} onChange={(event) => onChange({ [field]: event.target.value })}>
      {!options.some(([key]) => key === value(field)) ? <option value={value(field)}>{value(field) || '请选择'}</option> : null}
      {options.map(([key, title]) => <option key={key} value={key}>{title}</option>)}
    </Select>
  </FormField>
  const toggle = (field: string, label: string) => <div key={field} className="flex items-center justify-between gap-3">
    <label className="text-sm text-ink" htmlFor={`node-${node.id}-${field}`}>{label}</label>
    <Switch id={`node-${node.id}-${field}`} checked={node.config[field] === true} disabled={disabled} onCheckedChange={(checked) => onChange({ [field]: checked })} />
  </div>
  const selector = () => <>{text('selector', '元素选择器', '支持 CSS 选择器或以 xpath= 开头的 XPath。')}{selectorTools}</>
  const insertReference = (reference: string) => {
    const target = activeInput.current
    if (!target || !target.input.isConnected || disabled) return
    const current = value(target.field)
    onEditStart?.()
    onChange({ [target.field]: current.slice(0, target.start) + reference + current.slice(target.end) })
    onEditEnd?.()
    const cursor = target.start + reference.length
    requestAnimationFrame(() => {
      target.input.focus()
      target.input.setSelectionRange(cursor, cursor)
      bindTextTarget(target.field, target.input)
    })
  }

  return <section className="space-y-5 p-4" aria-label="节点配置">
    <div><h3 className="text-sm font-semibold text-ink">{definition?.title ?? node.type}</h3><p className="mt-1 text-xs leading-5 text-muted">{definition?.description}</p></div>
    <FormField htmlFor={`node-${node.id}-label`} label="节点名称"><Input value={node.label} disabled={disabled} onFocus={() => { clearTextTarget(); onEditStart?.() }} onBlur={onEditEnd} onChange={(event) => onLabelChange(event.target.value)} /></FormField>
    <div className="space-y-4 border-t border-line pt-4">
      {node.type === 'android_launch_app' ? text('packageName', '应用包名') : null}
      {node.type === 'android_manual' ? text('prompt', '人工处理说明', '到达此节点后等待人工明确继续。', true) : null}
      {node.type === 'android_screenshot' ? text('variableName', '输出变量', '输出截图引用及原始宽高。', false, false) : null}
      {node.type === 'android_key' ? select('key', '系统按键', [['HOME', '主页'], ['BACK', '返回'], ['ENTER', '确认'], ['APP_SWITCH', '最近应用']]) : null}
      {node.type === 'android_tap' ? <>{[['x', '横坐标'], ['y', '纵坐标'], ['basisWidth', '截图宽度'], ['basisHeight', '截图高度']].map(([field, label]) => <FormField key={field} label={label} htmlFor={`android-${field}`}><Input id={`android-${field}`} type="number" value={Number(node.config[field] ?? 0)} disabled={disabled} onFocus={onEditStart} onBlur={onEditEnd} onChange={e => onChange({ [field]: Number(e.target.value) })} /></FormField>)}<p className="text-xs text-muted">填写设备截图中的像素坐标，尺寸不符将停止操作。</p></> : null}
      {node.type === 'open_page' ? <>
        {text('url', '网页地址', '支持在地址中引用流程变量。')}
        {select('openMode', '打开方式', [['new_tab', '新标签页'], ['current_tab', '当前标签页']])}
        {select('waitUntil', '页面就绪条件', [['load', '完整加载（load）'], ['domcontentloaded', 'DOM 就绪'], ['networkidle', '网络空闲']])}
      </> : null}
      {node.type === 'click_element' ? <>{selector()}{select('clickType', '点击方式', [['single', '单击'], ['double', '双击'], ['right', '右键']])}{toggle('followNewTab', '跟随新标签页')}</> : null}
      {node.type === 'input_text' ? <>{selector()}{text('text', '输入文本', '允许空文本；可引用流程变量。', true)}{toggle('clearBefore', '输入前清空')}</> : null}
      {node.type === 'wait_element' ? <>{selector()}{select('waitCondition', '等待条件', [['visible', '可见'], ['hidden', '隐藏'], ['attached', '出现'], ['detached', '移除']])}</> : null}
      {node.type === 'get_element_info' ? <>{selector()}{select('attribute', '提取内容', [['text', '文本'], ['innerHTML', 'HTML'], ['value', 'value'], ['href', 'href'], ['src', 'src'], ['attributes', '属性字典']])}{text('variableName', '输出变量', '保存提取结果的变量名。', false, false)}</> : null}
      {node.type === 'screenshot' ? <>
        {select('screenshotType', '截图范围', [['fullpage', '整页'], ['viewport', '视口'], ['element', '元素']])}
        {node.config.screenshotType === 'element' ? selector() : null}
        {text('savePath', '保存路径', '留空表示执行时使用默认产物目录。')}
        {text('variableName', '输出变量', '保存截图路径的变量名。', false, false)}
      </> : null}
      {controlFields}
      <FormField htmlFor={`node-${node.id}-timeout`} label="超时（秒）" hint="节点执行时允许等待的最长时间。" error={fieldError('timeoutSeconds')}>
        <Input type="number" min="0" step="any" value={value('timeoutSeconds')} disabled={disabled} onFocus={() => { clearTextTarget(); onEditStart?.() }} onBlur={onEditEnd} onChange={(event) => {
          const raw = event.target.value
          onChange({ timeoutSeconds: raw !== '' && Number.isFinite(Number(raw)) ? Number(raw) : raw })
        }} />
      </FormField>
    </div>
    <div className="space-y-2 border-t border-line pt-4">
      <DropdownMenu><DropdownMenuTrigger asChild><Button type="button" className="w-full" disabled={disabled || !variables.length || !hasTarget}><BracketsCurly size={16} />插入变量引用</Button></DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="max-h-72 overflow-y-auto">
          {variables.flatMap((variable) => [`{${variable.name}}`, '${' + variable.name + '}'].map((reference) => <DropdownMenuItem key={reference} onSelect={() => insertReference(reference)}><code>{reference}</code></DropdownMenuItem>))}
        </DropdownMenuContent>
      </DropdownMenu>
      <p className="text-xs leading-5 text-muted">{!variables.length ? '先在流程变量中添加变量，再选择文本字段插入引用。' : '先将光标放入地址、选择器、输入文本或保存路径，再插入引用。'}</p>
    </div>
    {nodeIssues.length ? <div className="rounded-control border border-clay/20 bg-clay-soft/50 p-3"><p className="mb-2 text-xs font-semibold text-clay">待完成提示 · 可保存编辑进度</p><ul className="space-y-1 text-xs leading-5 text-muted">{nodeIssues.map((issue, index) => <li key={`${issue.code}-${index}`}>{issue.path.join(' / ')}：{issue.message}</li>)}</ul></div> : null}
  </section>
}
