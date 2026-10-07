import { Button } from '../../../../shared/components/ui/button'
import { Input } from '../../../../shared/components/ui/input'
import { Select } from '../../../../shared/components/ui/select'
import { Switch } from '../../../../shared/components/ui/switch'
import type { components } from '../../../../shared/api/generated'
import { autoMatchBindings } from './field-matching'
import { firstRelationFor, type RelationContext } from './relations'
import type { InputDefinition, RecordRef, SignatureGroup } from './types'

export const emptyFilter = () => ({ type: 'all', items: [] })
export const without = <T extends object>(value: T, keys: string[]) => { const next = { ...value } as Record<string, unknown>; keys.forEach(key => delete next[key]); return next as T }
export const choices = <T,>(items: T[], value: string | null | undefined, id: (item: T) => string, label: (item: T) => string, unavailable: string) => [
  ...(value && !items.some(item => id(item) === value) ? [{ value, label: unavailable, disabled: true }] : []),
  ...items.map(item => ({ value: id(item), label: label(item), disabled: false })),
]
const recordKey = (ref: RecordRef) => `${ref.projectId}:${ref.tableId}:${ref.datasetGeneration}:${ref.recordKey.type}:${ref.recordKey.value}`
const missingFields = (group: SignatureGroup, input: InputDefinition) =>
  group.fields.filter(field => field.required && !input.fieldBindings.some(binding => binding.signatureField === field.key))

export type InputSourceSectionProps = {
  input: InputDefinition
  context: RelationContext
  signature?: components['schemas']['WorkflowSignature'] | null
  referencedBy?: InputDefinition
  requiredBy?: InputDefinition
  relatedCandidates: InputDefinition[]
  disabled: boolean
  errors: Record<string, string | undefined>
  onChange(next: InputDefinition): void
  onRemove(): void
  onLoadRecords?(tableId: string): void
}

/** Where one input reads from: its name, workflow input, data table, mode and fixed record. */
export function InputSourceSection({ input, context, signature, referencedBy, requiredBy, relatedCandidates, disabled, errors, onChange, onRemove, onLoadRecords }: InputSourceSectionProps) {
  const { tables } = context
  const table = tables.find(item => item.id === input.tableId)
  const group = signature?.inputs.find(item => item.key === input.signatureInput)
  return <>
    <div className="flex min-w-0 flex-wrap items-start justify-between gap-3"><Input className="max-w-sm" aria-label={`输入别名 ${input.alias}`} value={input.alias} disabled={disabled} onChange={event => onChange({ ...input, alias: event.target.value })}/><Button size="sm" variant="ghost" aria-label={`移除输入 ${input.alias}`} disabled={disabled || Boolean(referencedBy)} onClick={onRemove}>移除输入</Button></div>
    {referencedBy ? <p className="m-0 text-sm text-warning">此输入正被“{referencedBy.alias}”引用，不能更换数据表或移除。</p> : null}
    {signature?.inputs.length ? <Select className="max-w-sm" aria-label={`对应流程输入 ${input.alias}`} value={input.signatureInput ?? null} placeholder="不对应流程输入" options={signature.inputs.map(item => ({ value: item.key, label: item.name, disabled: context.inputs.some(other => other.inputId !== input.inputId && other.signatureInput === item.key) }))} disabled={disabled} onValueChange={key => {
      const reset = { ...input, signatureInput: key ?? null, fieldBindings: input.fieldBindings.map(binding => ({ ...binding, signatureField: null })) }
      const next = signature.inputs.find(item => item.key === key)
      onChange(next && table ? { ...reset, fieldBindings: [...reset.fieldBindings, ...autoMatchBindings(next, reset.fieldBindings, table.fields)] } : reset)
    }}/> : null}
    {group && missingFields(group, input).length ? <p className="m-0 text-sm text-warning">流程输入「{group.name}」还缺少字段：{missingFields(group, input).map(field => field.name).join('、')}</p> : null}
    <div className="grid min-w-0 gap-3 sm:grid-cols-2">
      <Select aria-label={`数据表 ${input.alias}`} value={input.tableId} options={choices(tables, input.tableId, item => item.id, item => item.name, '数据表已失效')} clearable={false} disabled={disabled || Boolean(referencedBy) || input.mode === 'related'} errorMessage={errors[`${input.inputId}.tableId`]} onValueChange={tableId => {
        const nextTable = tables.find(item => item.id === tableId)
        if (!nextTable) return
        const reset = { ...without(input, ['fixedRecord', 'relation']), tableId: nextTable.id, datasetGeneration: nextTable.datasetGeneration, fieldBindings: [], filter: emptyFilter(), orderBy: [], fixedRecord: undefined }
        onChange(group ? { ...reset, fieldBindings: autoMatchBindings(group, [], nextTable.fields) } : reset)
      }}/>
      <Select aria-label={`输入模式 ${input.alias}`} value={input.mode} options={[{ value: 'independent', label: '独立选择记录' }, { value: 'fixedRecord', label: '固定记录' }, { value: 'related', label: '关联其他输入', disabled: !relatedCandidates.length }]} clearable={false} disabled={disabled} errorMessage={errors[`${input.inputId}.mode`]} onValueChange={mode => {
        if (mode === 'independent') onChange({ ...without(input, ['fixedRecord', 'relation']), mode })
        if (mode === 'fixedRecord') onChange({ ...without(input, ['relation']), mode, fixedRecord: null })
        if (mode === 'related' && relatedCandidates[0]) { const relation = firstRelationFor(context, input, relatedCandidates[0]); if (relation) onChange({ ...without(input, ['fixedRecord']), mode, relation }) }
      }}/>
    </div>
    <label className="flex items-center gap-3 text-sm"><Switch aria-label={`必填输入 ${input.alias}`} checked={input.required} disabled={disabled} onCheckedChange={required => onChange({ ...input, required })}/>启动时必须取得记录</label>
    {requiredBy ? <p className="m-0 text-sm text-warning">“{requiredBy.alias || '未命名输入'}”启动时必须取得记录，因此此输入也必须提供。</p> : null}
    {input.mode === 'fixedRecord' ? <div className="grid gap-2"><div className="flex flex-wrap gap-2"><Select className="min-w-64 flex-1" aria-label={`固定记录 ${input.alias}`} value={input.fixedRecord ? recordKey(input.fixedRecord) : null} options={choices(table?.records ?? [], input.fixedRecord ? recordKey(input.fixedRecord) : null, record => recordKey(record.ref), record => record.label, '记录已失效')} disabled={disabled} errorMessage={errors[`${input.inputId}.fixedRecord`]} onValueChange={key => onChange({ ...input, fixedRecord: table?.records?.find(record => recordKey(record.ref) === key)?.ref ?? null })}/>{onLoadRecords ? <Button disabled={disabled} onClick={() => onLoadRecords(input.tableId)}>读取{table?.name ?? '数据表'}记录</Button> : null}</div></div> : null}
  </>
}
