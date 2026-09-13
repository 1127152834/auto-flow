import { useState, type ReactNode } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { ValueSourceEditor, object } from './ValueSourceEditor'
import type { WorkflowNode } from '../types'

const initialRule = () => ({ kind: 'value', operator: 'eq', left: { kind: 'literal', value: true }, right: { kind: 'literal', value: true } })
const unary = new Set(['empty', 'not_empty', 'is_true', 'is_false'])
const labels: Record<string, string> = { eq: '相等', ne: '不等', gt: '大于', gte: '大于或等于', lt: '小于', lte: '小于或等于', contains: '包含', starts_with: '开头为', ends_with: '结尾为', in: '属于列表', empty: '为空', not_empty: '不为空', is_true: '为 true', is_false: '为 false' }
export type RuleTools = (rule: Record<string, unknown>, index: number, change: (patch: Record<string, unknown>) => void) => ReactNode

function LocalName({ value, label, onChange }: { value: string; label: string; onChange(value: string): void }) {
  const [draft, setDraft] = useState(value)
  const valid = /^[\p{L}_][\p{L}\p{N}_]*$/u.test(draft)
  return <label className="block space-y-1 text-xs">{label}<Input aria-label={label} value={draft} data-pending-variable-rename={draft !== value || undefined} onChange={event => setDraft(event.target.value)} onBlur={() => { if (valid && draft !== value) onChange(draft) }} />{!valid ? <span className="text-amber-800">请输入有效变量名</span> : null}</label>
}

function ConditionFields({ config, names, onChange, renderTools }: { config: Record<string, unknown>; names: string[]; onChange(patch: Record<string, unknown>): void; renderTools?: RuleTools }) {
  const rules = Array.isArray(config.rules) ? config.rules.map(object) : []
  const patch = (index: number, changes: Record<string, unknown>) => onChange({ rules: rules.map((rule, i) => i === index ? { ...rule, ...changes } : rule) })
  return <div className="space-y-3" aria-label="条件规则">
    <Select aria-label="条件匹配方式" className="w-full" value={String(config.match ?? 'all')} onChange={event => onChange({ match: event.target.value })}><option value="all">全部满足</option><option value="any">任一满足</option></Select>
    {rules.map((rule, index) => <section key={index} className="space-y-2 rounded-control border border-line p-2" aria-label={`规则${index + 1}`}>
      <div className="flex items-center justify-between text-xs"><span>规则 {index + 1}</span><Button variant="ghost" aria-label={`删除规则${index + 1}`} onClick={() => onChange({ rules: rules.filter((_, i) => i !== index) })}>删除</Button></div>
      <Select aria-label={`规则${index + 1}类型`} className="w-full" value={String(rule.kind)} onChange={event => onChange({ rules: rules.map((r, i) => i === index ? event.target.value === 'page' ? { kind: 'page', operator: 'exists', selector: '', framePath: [] } : initialRule() : r) })}><option value="value">值比较</option><option value="page">网页判断</option></Select>
      {rule.kind === 'page' ? <>
        <Select aria-label={`规则${index + 1}比较方式`} className="w-full" value={String(rule.operator)} onChange={event => patch(index, { operator: event.target.value })}>{Object.entries({ exists: '元素存在', not_exists: '元素不存在', visible: '首个匹配可见', not_visible: '首个匹配不可见' }).map(([key, title]) => <option key={key} value={key}>{title}</option>)}</Select>
        <Input aria-label={`规则${index + 1}选择器`} value={String(rule.selector ?? '')} placeholder="CSS 或 xpath=" onChange={event => patch(index, { selector: event.target.value })} />
        <Select aria-label={`规则${index + 1}插入变量引用`} className="w-full" value="" disabled={!names.length} onChange={event => { if (event.target.value) patch(index, { selector: `${String(rule.selector ?? '')}{${event.target.value}}` }) }}><option value="">在选择器末尾插入变量</option>{names.map(name => <option key={name} value={name}>{name}</option>)}</Select>
        {renderTools ? renderTools(rule, index, changes => patch(index, changes)) : <Input aria-label={`规则${index + 1}框架路径`} value={Array.isArray(rule.framePath) ? rule.framePath.join('\n') : ''} onChange={event => patch(index, { framePath: event.target.value ? event.target.value.split('\n') : [] })} />}
      </> : <>
        <ValueSourceEditor label={`规则${index + 1}左值`} value={rule.left} names={names} onChange={left => patch(index, { left })} />
        <Select aria-label={`规则${index + 1}比较方式`} className="w-full" value={String(rule.operator)} onChange={event => patch(index, { operator: event.target.value })}>{Object.entries(labels).map(([key, title]) => <option key={key} value={key}>{title}</option>)}</Select>
        {!unary.has(String(rule.operator)) ? <ValueSourceEditor label={`规则${index + 1}右值`} value={rule.right} names={names} onChange={right => patch(index, { right })} /> : null}
      </>}
    </section>)}
    <Button disabled={rules.length >= 100} onClick={() => onChange({ rules: [...rules, initialRule()] })}>添加条件</Button>
  </div>
}

export function ControlFields({ node, names, disabled, onChange, onLocalRename, renderTools }: { node: WorkflowNode; names: string[]; disabled?: boolean; onChange(patch: Record<string, unknown>): void; onLocalRename?(field: 'indexVariable' | 'itemVariable', value: string): void; renderTools?: RuleTools }) {
  const c = node.config
  return <fieldset disabled={disabled} className="space-y-4" aria-label="流程控制配置">
    {node.type === 'condition' || node.type === 'loop' && c.mode === 'while' ? <ConditionFields config={c} names={names} onChange={onChange} renderTools={renderTools} /> : null}
    {node.type === 'loop' ? <>
      <label className="block space-y-1 text-xs">循环方式<Select aria-label="循环方式" value={String(c.mode)} onChange={event => onChange({ mode: event.target.value, source: { kind: 'literal', value: event.target.value === 'foreach' ? [] : 1 } })}><option value="count">重复指定次数</option><option value="foreach">遍历列表</option><option value="while">条件成立时循环</option></Select></label>
      {c.mode !== 'while' ? <ValueSourceEditor label={c.mode === 'foreach' ? '遍历列表' : '循环次数'} value={c.source} onChange={source => onChange({ source })} names={names} /> : null}
      <LocalName key={`index-${c.indexVariable}`} value={String(c.indexVariable)} label="循环序号变量（一基）" onChange={value => onLocalRename ? onLocalRename('indexVariable', value) : onChange({ indexVariable: value })} />
      {c.mode === 'foreach' ? <LocalName key={`item-${c.itemVariable}`} value={String(c.itemVariable)} label="当前项变量" onChange={value => onLocalRename ? onLocalRename('itemVariable', value) : onChange({ itemVariable: value })} /> : null}
      <label className="block space-y-1 text-xs">最大循环次数<Input aria-label="最大循环次数" type="number" min={1} max={100000} value={String(c.maxIterations)} onChange={event => onChange({ maxIterations: event.target.value === '' ? '' : Number(event.target.value) })} /></label>
      <p className="text-xs text-muted">循环变量仅在循环体内可读。每个节点独立计时，停止将结束本次运行。</p>
    </> : null}
    {node.type === 'set_variable' ? <>
      <Input aria-label="写入变量名" placeholder="写入变量名" value={String(c.variableName ?? '')} onChange={event => onChange({ variableName: event.target.value })} />
      <Select aria-label="变量操作" className="w-full" value={String(c.operation)} onChange={event => onChange({ operation: event.target.value })}><option value="assign">设置</option><option value="add">增加</option><option value="subtract">减少</option><option value="append">列表追加</option></Select>
      <ValueSourceEditor label="写入值" value={c.value} names={names} onChange={value => onChange({ value })} />
    </> : null}
    {node.type.endsWith('_end') ? <p className="text-xs text-muted">此节点与控制起点配对，复制和删除由起点统一操作。</p> : null}
    {node.type === 'break_loop' || node.type === 'continue_loop' ? <p className="text-xs text-muted">{node.type === 'break_loop' ? '退出最近一层循环，继续循环之后的流程。' : '跳过最近一层循环本轮剩余操作，开始下一轮。'}</p> : null}
  </fieldset>
}
