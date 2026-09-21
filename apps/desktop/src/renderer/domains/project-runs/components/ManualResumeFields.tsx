import type { components } from '../../../shared/api/generated'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Textarea } from '../../../shared/components/ui/textarea'
import { assertFiniteNumbers } from '../../project-data/data-command'

type Field = components['schemas']['ManualInputFieldView']
export function parseManualInputs(fields: Field[], draft: Record<string, string>): { values: Record<string, unknown>; error?: string } {
  const values: Record<string, unknown> = {}
  for (const field of fields) {
    const raw = draft[field.name] ?? ''
    if (!raw.trim()) {
      if (field.required) return { values, error: `请填写 ${field.title || field.name}` }
      continue
    }
    try {
      const value: unknown = field.enum || field.type !== 'string' ? JSON.parse(raw) : raw
      const valid = field.type === 'string' ? typeof value === 'string' : field.type === 'boolean' ? typeof value === 'boolean' : field.type === 'integer' ? typeof value === 'number' && Number.isInteger(value) : field.type === 'number' ? typeof value === 'number' : field.type === 'array' ? Array.isArray(value) : value !== null && typeof value === 'object' && !Array.isArray(value)
      if (!valid || field.enum && !field.enum.some(item => JSON.stringify(item) === JSON.stringify(value))) throw new Error()
      assertFiniteNumbers(value)
      values[field.name] = value
    } catch { return { values, error: `${field.title || field.name} 的格式与声明不符` } }
  }
  return { values }
}

export function ManualResumeFields({ fields, draft, onChange, disabled }: { fields: Field[]; draft: Record<string, string>; onChange(value: Record<string, string>): void; disabled: boolean }) {
  const parsed = parseManualInputs(fields, draft)
  return <div className="grid gap-3">
    {fields.map(field => {
      const set = (value: string) => onChange({ ...draft, [field.name]: value })
      const title = field.title || field.name
      const options = field.enum?.map(value => ({ value: JSON.stringify(value), label: typeof value === 'string' ? value : JSON.stringify(value) })) ?? (field.type === 'boolean' ? [{ value: 'true', label: '是' }, { value: 'false', label: '否' }] : null)
      return <label key={field.name} className="grid gap-2 text-sm"><span>{title}{field.required ? ' *' : ''}</span>{options ? <Select aria-label={title} options={options} value={draft[field.name] || null} onValueChange={value => set(value ?? '')} disabled={disabled}/> : field.type === 'array' || field.type === 'object' ? <Textarea aria-label={title} value={draft[field.name] ?? ''} onChange={event => set(event.target.value)} disabled={disabled} placeholder={field.type === 'array' ? '["值"]' : '{"字段":"值"}'}/> : <Input aria-label={title} value={draft[field.name] ?? ''} onChange={event => set(event.target.value)} disabled={disabled}/>}</label>
    })}
    {parsed.error ? <p role="alert" className="m-0 text-sm text-danger">{parsed.error}</p> : null}
  </div>
}
