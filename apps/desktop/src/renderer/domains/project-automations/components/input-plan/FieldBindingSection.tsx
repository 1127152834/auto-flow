import { Button } from '../../../../shared/components/ui/button'
import { Input } from '../../../../shared/components/ui/input'
import { Select } from '../../../../shared/components/ui/select'
import { autoMatchBindings, typeMismatch, typeName } from './field-matching'
import { choices } from './InputSourceSection'
import type { InputDefinition, InputTableOption, SignatureGroup } from './types'

export type FieldBindingSectionProps = {
  input: InputDefinition
  table?: InputTableOption
  group?: SignatureGroup
  disabled: boolean
  onChange(next: InputDefinition): void
}

/** Left: the fields the workflow asks for. Right: the table field each one reads from. */
function SignatureBindings({ input, table, group, disabled, onChange }: Required<Pick<FieldBindingSectionProps, 'group'>> & Omit<FieldBindingSectionProps, 'group'>) {
  const fields = table?.fields ?? []
  const proposals = autoMatchBindings(group, input.fieldBindings, fields)
  const bind = (signatureKey: string, fieldId: string | null) => {
    const signatureField = group.fields.find(item => item.key === signatureKey)
    const existing = input.fieldBindings.findIndex(binding => binding.signatureField === signatureKey)
    const target = fields.find(item => item.ref.fieldId === fieldId)
    if (!fieldId || !target) return onChange({ ...input, fieldBindings: input.fieldBindings.filter((_, index) => index !== existing) })
    if (existing >= 0) return onChange({ ...input, fieldBindings: input.fieldBindings.map((binding, index) => index === existing ? { ...binding, fieldRef: target.ref } : binding) })
    onChange({ ...input, fieldBindings: [...input.fieldBindings, { inputFieldId: crypto.randomUUID(), inputFieldAlias: signatureField?.name ?? target.name, fieldRef: target.ref, signatureField: signatureKey }] })
  }
  return <div role="group" aria-label={`流程字段对应 ${input.alias}`} className="grid min-w-0 gap-2 rounded-control border border-line bg-surface-subtle p-3">
    <div className="flex flex-wrap items-center justify-between gap-2"><p className="m-0 text-sm font-medium">「{group.name}」需要的字段</p><Button size="sm" disabled={disabled || !proposals.length} onClick={() => onChange({ ...input, fieldBindings: [...input.fieldBindings, ...proposals] })}>按名称自动匹配</Button></div>
    {group.fields.map(field => {
      const binding = input.fieldBindings.find(item => item.signatureField === field.key)
      const target = fields.find(item => item.ref.fieldId === binding?.fieldRef.fieldId)
      const missing = field.required && !binding
      const mismatch = target ? typeMismatch(field.type, target.type) : null
      return <div key={field.key} className="grid min-w-0 gap-1 sm:grid-cols-[minmax(10rem,1fr)_minmax(12rem,1.2fr)] sm:items-start sm:gap-3" data-invalid={missing || undefined}>
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 text-sm"><span className={missing ? 'font-medium text-danger' : 'font-medium'}>{field.name}</span><span className="whitespace-nowrap text-xs text-muted">{typeName(field.type)}{field.required ? ' · 必填' : ' · 选填'}{field.sensitive ? ' · 敏感' : ''}</span></div>
        <div className="grid min-w-0 gap-1">
          <Select aria-label={`对应表字段 ${field.name}`} aria-invalid={missing || undefined} value={binding?.fieldRef.fieldId ?? null} placeholder={missing ? '请选择对应的表字段' : '不绑定'} options={choices(fields, binding?.fieldRef.fieldId, item => item.ref.fieldId, item => `${item.name}（${typeName(item.type)}）`, '字段已失效')} disabled={disabled} onValueChange={fieldId => bind(field.key, fieldId)}/>
          {missing ? <p role="alert" className="m-0 text-xs text-danger">请选择对应的表字段</p> : null}
          {mismatch ? <p className="m-0 text-xs text-warning">类型不一致：{mismatch}</p> : null}
        </div>
      </div>
    })}
  </div>
}

export function FieldBindingSection({ input, table, group, disabled, onChange }: FieldBindingSectionProps) {
  const replaceBinding = (index: number, patch: Partial<InputDefinition['fieldBindings'][number]>) =>
    onChange({ ...input, fieldBindings: input.fieldBindings.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item) })
  return <>
    {group ? <SignatureBindings input={input} table={table} group={group} disabled={disabled} onChange={onChange}/> : null}
    <details open={input.fieldBindings.length > 0 || undefined} className="rounded-control border border-line bg-surface-subtle">
      <summary className="cursor-pointer px-3 py-2 text-sm font-medium">字段映射 <span className="ml-2 font-normal text-muted">{input.fieldBindings.length ? `${input.fieldBindings.length} 项` : '未设置'}</span></summary>
      <fieldset className="grid gap-3 border-t border-line p-3"><legend className="sr-only">字段映射</legend>
        {input.fieldBindings.map((binding, bindingIndex) => <div className="grid min-w-0 gap-2 sm:grid-cols-[repeat(auto-fit,minmax(10rem,1fr))]" key={binding.inputFieldId}>
          <Input aria-label={`字段别名 ${binding.inputFieldAlias}`} value={binding.inputFieldAlias} disabled={disabled} onChange={event => replaceBinding(bindingIndex, { inputFieldAlias: event.target.value })}/>
          <Select aria-label={`映射字段 ${binding.inputFieldAlias}`} value={binding.fieldRef.fieldId} options={choices(table?.fields ?? [], binding.fieldRef.fieldId, field => field.ref.fieldId, field => field.name, '字段已失效')} clearable={false} disabled={disabled} onValueChange={fieldId => { const field = table?.fields.find(item => item.ref.fieldId === fieldId); if (field) replaceBinding(bindingIndex, { fieldRef: field.ref }) }}/>
          {group ? <Select aria-label={`对应流程字段 ${binding.inputFieldAlias}`} value={binding.signatureField ?? null} placeholder="不对应流程字段" options={group.fields.map(field => ({ value: field.key, label: field.name, disabled: input.fieldBindings.some((other, otherIndex) => otherIndex !== bindingIndex && other.signatureField === field.key) }))} disabled={disabled} onValueChange={key => replaceBinding(bindingIndex, { signatureField: key ?? null })}/> : null}
          <Button size="sm" variant="ghost" disabled={disabled} onClick={() => onChange({ ...input, fieldBindings: input.fieldBindings.filter((_, itemIndex) => itemIndex !== bindingIndex) })}>移除映射</Button>
        </div>)}
        <Button className="justify-self-start" size="sm" disabled={disabled || !table?.fields.length} aria-label={`添加字段映射 ${input.alias}`} onClick={() => { const field = table?.fields.find(candidate => !input.fieldBindings.some(binding => binding.fieldRef.fieldId === candidate.ref.fieldId)); if (field) onChange({ ...input, fieldBindings: [...input.fieldBindings, { inputFieldId: crypto.randomUUID(), inputFieldAlias: field.name, fieldRef: field.ref }] }) }}>添加字段映射</Button>
      </fieldset>
    </details>
  </>
}
