import { Select } from '../../../../shared/components/ui/select'
import { choices } from './InputSourceSection'
import { firstRelationFor, relationCapabilities, relationFor, type RelationContext } from './relations'
import type { InputDefinition } from './types'

export type InputRelationSectionProps = {
  input: InputDefinition
  index: number
  context: RelationContext
  relatedCandidates: InputDefinition[]
  disabled: boolean
  onChange(next: InputDefinition): void
}

/** How a related input finds its record from an earlier input. */
export function InputRelationSection({ input, index, context, relatedCandidates, disabled, onChange }: InputRelationSectionProps) {
  const table = context.tables.find(item => item.id === input.tableId)
  const sourceCandidates = context.inputs.slice(0, index)
  const sourceInput = context.inputs.find(item => item.inputId === input.relation?.sourceInputId)
  const sourceTable = context.tables.find(item => item.id === sourceInput?.tableId)
  const slots = (sourceTable?.slotDefinitions ?? []).filter(slot => slot.targetTableId === input.tableId)
  const sourceFields = (sourceTable?.fields ?? []).filter(field => table?.fields.some(target => target.type === field.type))
  const relationSourceFieldId = input.relation?.type === 'fieldEquals' ? input.relation.sourceFieldRef.fieldId : undefined
  const relationSourceFieldType = sourceTable?.fields.find(field => field.ref.fieldId === relationSourceFieldId)?.type
  const relationType = input.relation?.type ?? 'sameRecord'
  const capabilities = sourceInput ? relationCapabilities(context, input, sourceInput) : { sameRecord: false, fieldEquals: false, recordSlot: false }
  return <fieldset tabIndex={-1} data-relation-editor={input.inputId} className="grid gap-3 rounded-control bg-surface-subtle p-3"><legend className="text-sm font-medium">关联输入</legend>
    <div className="grid gap-2 sm:grid-cols-2">
      <Select aria-label={`来源输入 ${input.alias}`} value={input.relation?.sourceInputId ?? null} options={choices(sourceCandidates, input.relation?.sourceInputId, item => item.inputId, item => item.alias || '未命名输入', '数据输入引用暂不可用').map(option => ({ ...option, disabled: option.disabled || Boolean(sourceCandidates.find(item => item.inputId === option.value) && !relatedCandidates.includes(sourceCandidates.find(item => item.inputId === option.value)!)) }))} clearable={false} disabled={disabled} onValueChange={sourceInputId => {
        if (!sourceInputId) return
        const candidate = sourceCandidates.find(item => item.inputId === sourceInputId)
        if (!candidate) return
        const relation = relationFor(context, input, relationType, sourceInputId) ?? firstRelationFor(context, input, candidate)
        if (relation) onChange({ ...input, relation })
      }}/>
      <Select aria-label={`关联方式 ${input.alias}`} value={relationType} options={[{ value: 'sameRecord', label: '同一记录', disabled: !capabilities.sameRecord }, { value: 'fieldEquals', label: '字段相等', disabled: !capabilities.fieldEquals }, { value: 'recordSlot', label: '记录槽', disabled: !capabilities.recordSlot }]} clearable={false} disabled={disabled} onValueChange={type => {
        if (!type || !sourceInput) return
        const relation = relationFor(context, input, type, sourceInput.inputId)
        if (relation) onChange({ ...input, relation })
      }}/>
    </div>
    {input.relation?.type === 'fieldEquals' ? <div className="grid gap-2 sm:grid-cols-2">
      <Select aria-label={`来源字段 ${input.alias}`} value={input.relation.sourceFieldRef.fieldId} options={choices(sourceFields, input.relation.sourceFieldRef.fieldId, field => field.ref.fieldId, field => field.name, '字段已失效')} clearable={false} disabled={disabled} onValueChange={fieldId => { const field = sourceFields.find(item => item.ref.fieldId === fieldId), target = table?.fields.find(item => item.type === field?.type); if (field && target && input.relation?.type === 'fieldEquals') onChange({ ...input, relation: { ...input.relation, sourceFieldRef: field.ref, targetFieldRef: target.ref } }) }}/>
      <Select aria-label={`目标字段 ${input.alias}`} value={input.relation.targetFieldRef.fieldId} options={choices((table?.fields ?? []).filter(field => field.type === relationSourceFieldType), input.relation.targetFieldRef.fieldId, field => field.ref.fieldId, field => field.name, '字段已失效')} clearable={false} disabled={disabled} onValueChange={fieldId => { const field = table?.fields.find(item => item.ref.fieldId === fieldId); if (field && input.relation?.type === 'fieldEquals') onChange({ ...input, relation: { ...input.relation, targetFieldRef: field.ref } }) }}/>
    </div> : null}
    {input.relation?.type === 'recordSlot' ? <Select aria-label={`记录槽 ${input.alias}`} value={input.relation.slotId} options={choices(slots, input.relation.slotId, slot => slot.slotId, slot => slot.name, '记录槽已失效')} clearable={false} disabled={disabled} onValueChange={slotId => { if (slotId && input.relation?.type === 'recordSlot') onChange({ ...input, relation: { ...input.relation, slotId } }) }}/> : null}
    {!slots.length ? <p className="m-0 text-xs text-muted">来源表没有指向当前表的记录槽，不能选择记录槽关系。</p> : null}
  </fieldset>
}
