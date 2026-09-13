import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Textarea } from '../../../shared/components/ui/textarea'
import { Button } from '../../../shared/components/ui/button'

export type ValueSource = Record<string, unknown>
export const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
const literalType = (value: unknown) => value === null ? 'null' : Array.isArray(value) ? 'array' : typeof value
const defaults: Record<string, unknown> = { string: '', number: 0, boolean: false, array: [], object: {}, null: null }

export function ValueSourceEditor({ value, onChange, names, label, disabled }: { value: unknown; onChange(value: ValueSource): void; names: string[]; label: string; disabled?: boolean }) {
  const source = object(value)
  const kind = source.kind === 'variable' ? 'variable' : 'literal'
  const type = String(source.valueType ?? literalType(source.value === undefined ? '' : source.value))
  const steps = Array.isArray(source.path) ? source.path : []
  const text = typeof source.value === 'string' ? source.value : JSON.stringify(source.value ?? '')
  const parse = (raw: string) => {
    let parsed: unknown = raw
    if (type !== 'string') { try { parsed = JSON.parse(raw) } catch { /* Keep incomplete input in the document; validation blocks execution. */ } }
    onChange({ kind: 'literal', valueType: type, value: parsed })
  }
  const invalid = kind === 'literal' && literalType(source.value) !== type
  return <fieldset className="space-y-2 rounded-control border border-line p-2" disabled={disabled} aria-label={label}>
    <legend className="px-1 text-xs text-muted">{label}</legend>
    <Select aria-label={`${label}来源`} className="w-full" value={kind} onChange={event => onChange(event.target.value === 'literal' ? { kind: 'literal', value: '' } : { kind: 'variable', name: '', path: [] })}><option value="literal">固定值</option><option value="variable">变量</option></Select>
    {kind === 'variable' ? <>
      <Input aria-label={`${label}变量`} list={`${label}-variables`} value={String(source.name ?? '')} placeholder="选择或输入变量名" onChange={event => onChange({ ...source, name: event.target.value })} />
      <datalist id={`${label}-variables`}>{names.map(name => <option key={name} value={name} />)}</datalist>
      {steps.map((step, index) => <div key={index} className="flex gap-1"><Select aria-label={`${label}路径${index + 1}类型`} value={typeof step === 'number' ? 'index' : 'key'} onChange={event => onChange({ ...source, path: steps.map((s, i) => i === index ? event.target.value === 'index' ? 0 : '' : s) })}><option value="key">字段</option><option value="index">索引</option></Select><Input aria-label={`${label}路径${index + 1}`} type={typeof step === 'number' ? 'number' : 'text'} min={0} value={String(step)} onChange={event => onChange({ ...source, path: steps.map((s, i) => i === index ? typeof step === 'number' ? Number(event.target.value) : event.target.value : s) })} /><Button aria-label={`删除${label}路径${index + 1}`} onClick={() => onChange({ ...source, path: steps.filter((_, i) => i !== index) })}>×</Button></div>)}
      <Button disabled={steps.length >= 32} onClick={() => onChange({ ...source, path: [...steps, ''] })}>添加字段或索引</Button>
    </> : <>
      <Select aria-label={`${label}类型`} className="w-full" value={type} onChange={event => onChange({ kind: 'literal', valueType: event.target.value, value: defaults[event.target.value] })}>{Object.entries({ string: '字符串', number: '数字', boolean: '布尔', array: '列表 JSON', object: '对象 JSON', null: 'null' }).map(([key, title]) => <option key={key} value={key}>{title}</option>)}</Select>
      {type === 'null' ? <p className="text-xs text-muted">null</p> : type === 'boolean' ? <Select aria-label={`${label}值`} value={String(source.value)} onChange={event => onChange({ kind: 'literal', valueType: type, value: event.target.value === 'true' })}><option value="true">true</option><option value="false">false</option></Select> : type === 'array' || type === 'object' ? <Textarea aria-label={`${label}值`} rows={3} value={text} onChange={event => parse(event.target.value)} /> : <Input aria-label={`${label}值`} value={text} onChange={event => parse(event.target.value)} />}
      {invalid ? <p role="alert" className="text-xs text-amber-800">输入尚未符合所选类型，可以保存，运行前须完成。</p> : null}
    </>}
  </fieldset>
}
