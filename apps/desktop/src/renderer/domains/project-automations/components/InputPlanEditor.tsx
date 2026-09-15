import { useEffect, useRef, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Switch } from '../../../shared/components/ui/switch'
import type { components } from '../../../shared/api/generated'
import { RecordFilterEditor } from '../../project-data/components/RecordFilterEditor'
import type { FilterExpression, OrderBy, RecordQuery } from '../../project-data/record-query'
import type { Automation } from '../types'

type Plan = Automation['inputPlan']
type InputDefinition = Plan['inputs'][number]
type RecordRef = NonNullable<InputDefinition['fixedRecord']>
type Schema = components['schemas']
type FieldOption = Schema['DataFieldView']
export type InputTableOption = { id: string; name: string; datasetGeneration: string; identity?: Schema['DataTableView']['identity']; fields: FieldOption[]; statuses: Schema['DataStatusView'][]; slotDefinitions: Schema['TableSlotDefinition'][]; records?: { label: string; ref: RecordRef }[] }

export type InputPlanEditorProps = {
  value: Plan
  onChange(value: Plan): void
  tables: InputTableOption[]
  disabled?: boolean
  errors?: Record<string, string | undefined>
  resetKey?: string
  onDraftStateChange?(state: { dirty: boolean; valid: boolean }): void
  onLoadRecords?(tableId: string): void
}

const emptyFilter = () => ({ type: 'all', items: [] })
const choices = <T,>(items: T[], value: string | null | undefined, id: (item: T) => string, label: (item: T) => string, unavailable: string) => [
  ...(value && !items.some(item => id(item) === value) ? [{ value, label: unavailable, disabled: true }] : []),
  ...items.map(item => ({ value: id(item), label: label(item), disabled: false })),
]
const recordKey = (ref: RecordRef) => `${ref.projectId}:${ref.tableId}:${ref.datasetGeneration}:${ref.recordKey.type}:${ref.recordKey.value}`
const without = <T extends object>(value: T, keys: string[]) => { const next = { ...value } as Record<string, unknown>; keys.forEach(key => delete next[key]); return next as T }

export function InputPlanEditor({ value, onChange, tables, disabled = false, errors = {}, resetKey = '', onDraftStateChange, onLoadRecords }: InputPlanEditorProps) {
  const [filterDrafts, setFilterDrafts] = useState<Record<string, boolean>>({})
  const draftCallback = useRef(onDraftStateChange)
  useEffect(() => { draftCallback.current = onDraftStateChange }, [onDraftStateChange])
  useEffect(() => { setFilterDrafts({}) }, [resetKey])
  const filterDirty = value.inputs.some(input => filterDrafts[input.inputId])
  useEffect(() => { draftCallback.current?.({ dirty: filterDirty, valid: !filterDirty }) }, [filterDirty])
  const replace = (index: number, next: InputDefinition) => onChange({ inputs: value.inputs.map((input, itemIndex) => itemIndex === index ? next : input) })
  const referencedBy = (inputId: string) => value.inputs.find(input => input.mode === 'related' && input.relation?.sourceInputId === inputId)
  const add = () => {
    const table = tables[0]
    if (!table) return
    onChange({ inputs: [...value.inputs, { inputId: crypto.randomUUID(), alias: '', tableId: table.id, datasetGeneration: table.datasetGeneration, mode: 'independent', required: false, fieldBindings: [], filter: emptyFilter(), orderBy: [] }] })
  }
  return <section className="grid gap-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="m-0 text-base font-semibold">项目数据输入</h3><p className="mt-1 text-sm text-muted">{value.inputs.length ? '启动前会重新检查完整输入组并原子领取。' : '当前自动化不读取项目数据，可以直接使用参数启动。'}</p></div><Button size="sm" disabled={disabled || !tables.length} onClick={add}>添加数据输入</Button></div>
    {value.inputs.map((input, index) => {
      const table = tables.find(item => item.id === input.tableId)
      const reference = referencedBy(input.inputId)
      const modeError = errors[`${input.inputId}.mode`]
      const tableError = errors[`${input.inputId}.tableId`]
      const inputErrors = Object.entries(errors).filter(([path, message]) => path.startsWith(`${input.inputId}.`) && Boolean(message))
      const boundFieldIds = new Set(input.fieldBindings.map(binding => binding.fieldRef.fieldId))
      const boundFields = (table?.fields ?? []).filter(field => boundFieldIds.has(field.ref.fieldId))
      const sourceCandidates = value.inputs.slice(0, index)
      const sourceInput = input.mode === 'related' ? value.inputs.find(item => item.inputId === input.relation?.sourceInputId) : undefined
      const sourceTable = tables.find(item => item.id === sourceInput?.tableId)
      const slots = (sourceTable?.slotDefinitions ?? []).filter(slot => slot.targetTableId === input.tableId)
      const sourceFields = (sourceTable?.fields ?? []).filter(field => table?.fields.some(target => target.type === field.type))
      const relationSourceFieldId = input.mode === 'related' && input.relation?.type === 'fieldEquals' ? input.relation.sourceFieldRef.fieldId : undefined
      const relationSourceFieldType = sourceTable?.fields.find(field => field.ref.fieldId === relationSourceFieldId)?.type
      const relationType = input.mode === 'related' ? input.relation?.type ?? 'sameRecord' : 'sameRecord'
      const hasAppliedQuery = input.filter.type !== 'all' || (Array.isArray(input.filter.items) && input.filter.items.length > 0) || input.orderBy.length > 0
      const relationCapabilities = (candidate: InputDefinition) => {
        const candidateTable = tables.find(item => item.id === candidate.tableId)
        return {
          sameRecord: candidate.tableId === input.tableId && candidate.datasetGeneration === input.datasetGeneration,
          fieldEquals: Boolean(candidateTable?.fields.some(field => table?.fields.some(target => target.type === field.type))),
          recordSlot: Boolean(candidateTable?.slotDefinitions.some(slot => slot.targetTableId === input.tableId)),
        }
      }
      const relationFor = (type: string, sourceId: string) => {
        const selectedSource = value.inputs.find(item => item.inputId === sourceId)
        if (!selectedSource || !relationCapabilities(selectedSource)[type as keyof ReturnType<typeof relationCapabilities>]) return null
        const selectedSourceTable = tables.find(item => item.id === selectedSource?.tableId)
        const selectedSlots = (selectedSourceTable?.slotDefinitions ?? []).filter(slot => slot.targetTableId === input.tableId)
        if (type === 'sameRecord') return { type: 'sameRecord' as const, sourceInputId: sourceId }
        if (type === 'fieldEquals') { const sourceField = selectedSourceTable?.fields.find(field => table?.fields.some(target => target.type === field.type)), targetField = table?.fields.find(field => field.type === sourceField?.type); return sourceField && targetField ? { type: 'fieldEquals' as const, sourceInputId: sourceId, sourceFieldRef: sourceField.ref, targetFieldRef: targetField.ref } : null }
        return selectedSlots[0] ? { type: 'recordSlot' as const, sourceInputId: sourceId, slotId: selectedSlots[0].slotId } : null
      }
      const firstRelationFor = (candidate: InputDefinition) => {
        const capabilities = relationCapabilities(candidate)
        const type = (['sameRecord', 'fieldEquals', 'recordSlot'] as const).find(item => capabilities[item])
        return type ? relationFor(type, candidate.inputId) : null
      }
      const relatedCandidates = sourceCandidates.filter(candidate => Object.values(relationCapabilities(candidate)).some(Boolean))
      const capabilities = sourceInput ? relationCapabilities(sourceInput) : { sameRecord: false, fieldEquals: false, recordSlot: false }
      return <article key={input.inputId} className="grid min-w-0 gap-3 rounded-control border border-line bg-surface p-3" tabIndex={inputErrors.length ? -1 : undefined} aria-invalid={inputErrors.length ? true : undefined}>
        {inputErrors.length ? <p role="alert" className="m-0 text-sm text-danger">{inputErrors[0][1]}</p> : null}
        <div className="flex min-w-0 flex-wrap items-start justify-between gap-3"><Input className="max-w-sm" aria-label={`输入别名 ${input.alias}`} value={input.alias} disabled={disabled} onChange={event => replace(index, { ...input, alias: event.target.value })}/><Button size="sm" variant="ghost" aria-label={`移除输入 ${input.alias}`} disabled={disabled || Boolean(reference)} onClick={() => onChange({ inputs: value.inputs.filter((_, itemIndex) => itemIndex !== index) })}>移除输入</Button></div>
        {reference ? <p className="m-0 text-sm text-warning">此输入正被“{reference.alias}”引用，不能更换数据表或移除。</p> : null}
        <div className="grid min-w-0 gap-3 sm:grid-cols-2">
          <Select aria-label={`数据表 ${input.alias}`} value={input.tableId} options={choices(tables, input.tableId, item => item.id, item => item.name, '数据表已失效')} clearable={false} disabled={disabled || Boolean(reference) || input.mode === 'related'} errorMessage={tableError} onValueChange={tableId => {
            const nextTable = tables.find(item => item.id === tableId)
            if (!nextTable) return
            replace(index, { ...without(input, ['fixedRecord', 'relation']), tableId: nextTable.id, datasetGeneration: nextTable.datasetGeneration, fieldBindings: [], filter: emptyFilter(), orderBy: [], fixedRecord: undefined })
          }}/>
          <Select aria-label={`输入模式 ${input.alias}`} value={input.mode} options={[{ value: 'independent', label: '独立选择记录' }, { value: 'fixedRecord', label: '固定记录' }, { value: 'related', label: '关联其他输入', disabled: !relatedCandidates.length }]} clearable={false} disabled={disabled} errorMessage={modeError} onValueChange={mode => {
            if (mode === 'independent') replace(index, { ...without(input, ['fixedRecord', 'relation']), mode })
            if (mode === 'fixedRecord') replace(index, { ...without(input, ['relation']), mode, fixedRecord: null })
            if (mode === 'related' && relatedCandidates[0]) { const relation = firstRelationFor(relatedCandidates[0]); if (relation) replace(index, { ...without(input, ['fixedRecord']), mode, relation }) }
          }}/>
        </div>
        <label className="flex items-center gap-3 text-sm"><Switch aria-label={`必填输入 ${input.alias}`} checked={input.required} disabled={disabled} onCheckedChange={required => replace(index, { ...input, required })}/>启动时必须取得记录</label>
        {input.mode === 'fixedRecord' ? <div className="grid gap-2"><div className="flex flex-wrap gap-2"><Select className="min-w-64 flex-1" aria-label={`固定记录 ${input.alias}`} value={input.fixedRecord ? recordKey(input.fixedRecord) : null} options={choices(table?.records ?? [], input.fixedRecord ? recordKey(input.fixedRecord) : null, record => recordKey(record.ref), record => record.label, '记录已失效')} disabled={disabled} errorMessage={errors[`${input.inputId}.fixedRecord`]} onValueChange={key => replace(index, { ...input, fixedRecord: table?.records?.find(record => recordKey(record.ref) === key)?.ref ?? null })}/>{onLoadRecords ? <Button disabled={disabled} onClick={() => onLoadRecords(input.tableId)}>读取{table?.name ?? '数据表'}记录</Button> : null}</div></div> : null}
        {input.mode === 'related' ? <fieldset className="grid gap-3 rounded-control bg-surface-subtle p-3"><legend className="text-sm font-medium">关联输入</legend>
          <div className="grid gap-2 sm:grid-cols-2"><Select aria-label={`来源输入 ${input.alias}`} value={input.relation?.sourceInputId ?? null} options={choices(sourceCandidates, input.relation?.sourceInputId, item => item.inputId, item => item.alias || '未命名输入', '数据输入引用暂不可用').map(option => ({ ...option, disabled: option.disabled || Boolean(sourceCandidates.find(item => item.inputId === option.value) && !relatedCandidates.includes(sourceCandidates.find(item => item.inputId === option.value)!)) }))} clearable={false} disabled={disabled} onValueChange={sourceInputId => { if (!sourceInputId) return; const candidate = sourceCandidates.find(item => item.inputId === sourceInputId); if (!candidate) return; const relation = relationFor(relationType, sourceInputId) ?? firstRelationFor(candidate); if (relation) replace(index, { ...input, relation }) }}/><Select aria-label={`关联方式 ${input.alias}`} value={relationType} options={[{ value: 'sameRecord', label: '同一记录', disabled: !capabilities.sameRecord }, { value: 'fieldEquals', label: '字段相等', disabled: !capabilities.fieldEquals }, { value: 'recordSlot', label: '记录槽', disabled: !capabilities.recordSlot }]} clearable={false} disabled={disabled} onValueChange={type => { if (!type || !sourceInput) return; const relation = relationFor(type, sourceInput.inputId); if (relation) replace(index, { ...input, relation }) }}/></div>
          {input.relation?.type === 'fieldEquals' ? <div className="grid gap-2 sm:grid-cols-2"><Select aria-label={`来源字段 ${input.alias}`} value={input.relation.sourceFieldRef.fieldId} options={choices(sourceFields, input.relation.sourceFieldRef.fieldId, field => field.ref.fieldId, field => field.name, '字段已失效')} clearable={false} disabled={disabled} onValueChange={fieldId => { const field = sourceFields.find(item => item.ref.fieldId === fieldId), target = table?.fields.find(item => item.type === field?.type); if (field && target && input.relation?.type === 'fieldEquals') replace(index, { ...input, relation: { ...input.relation, sourceFieldRef: field.ref, targetFieldRef: target.ref } }) }}/><Select aria-label={`目标字段 ${input.alias}`} value={input.relation.targetFieldRef.fieldId} options={choices((table?.fields ?? []).filter(field => field.type === relationSourceFieldType), input.relation.targetFieldRef.fieldId, field => field.ref.fieldId, field => field.name, '字段已失效')} clearable={false} disabled={disabled} onValueChange={fieldId => { const field = table?.fields.find(item => item.ref.fieldId === fieldId); if (field && input.relation?.type === 'fieldEquals') replace(index, { ...input, relation: { ...input.relation, targetFieldRef: field.ref } }) }}/></div> : null}
          {input.relation?.type === 'recordSlot' ? <Select aria-label={`记录槽 ${input.alias}`} value={input.relation.slotId} options={choices(slots, input.relation.slotId, slot => slot.slotId, slot => slot.name, '记录槽已失效')} clearable={false} disabled={disabled} onValueChange={slotId => { if (slotId && input.relation?.type === 'recordSlot') replace(index, { ...input, relation: { ...input.relation, slotId } }) }}/> : null}
          {!slots.length ? <p className="m-0 text-xs text-muted">来源表没有指向当前表的记录槽，不能选择记录槽关系。</p> : null}
        </fieldset> : null}
        <details open={input.fieldBindings.length > 0 || undefined} className="rounded-control border border-line bg-surface-subtle">
          <summary className="cursor-pointer px-3 py-2 text-sm font-medium">字段映射 <span className="ml-2 font-normal text-muted">{input.fieldBindings.length ? `${input.fieldBindings.length} 项` : '未设置'}</span></summary>
          <fieldset className="grid gap-3 border-t border-line p-3"><legend className="sr-only">字段映射</legend>{input.fieldBindings.map((binding, bindingIndex) => <div className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]" key={binding.inputFieldId}><Input aria-label={`字段别名 ${binding.inputFieldAlias}`} value={binding.inputFieldAlias} disabled={disabled} onChange={event => replace(index, { ...input, fieldBindings: input.fieldBindings.map((item, itemIndex) => itemIndex === bindingIndex ? { ...item, inputFieldAlias: event.target.value } : item) })}/><Select aria-label={`映射字段 ${binding.inputFieldAlias}`} value={binding.fieldRef.fieldId} options={choices(table?.fields ?? [], binding.fieldRef.fieldId, field => field.ref.fieldId, field => field.name, '字段已失效')} clearable={false} disabled={disabled} onValueChange={fieldId => { const field = table?.fields.find(item => item.ref.fieldId === fieldId); if (field) replace(index, { ...input, fieldBindings: input.fieldBindings.map((item, itemIndex) => itemIndex === bindingIndex ? { ...item, fieldRef: field.ref } : item) }) }}/><Button size="sm" variant="ghost" disabled={disabled} onClick={() => replace(index, { ...input, fieldBindings: input.fieldBindings.filter((_, itemIndex) => itemIndex !== bindingIndex) })}>移除映射</Button></div>)}<Button className="justify-self-start" size="sm" disabled={disabled || !table?.fields.length} aria-label={`添加字段映射 ${input.alias}`} onClick={() => { const field = table?.fields.find(candidate => !input.fieldBindings.some(binding => binding.fieldRef.fieldId === candidate.ref.fieldId)); if (field) replace(index, { ...input, fieldBindings: [...input.fieldBindings, { inputFieldId: crypto.randomUUID(), inputFieldAlias: field.name, fieldRef: field.ref }] }) }}>添加字段映射</Button></fieldset>
        </details>
        {table ? <details open={hasAppliedQuery || undefined} className="rounded-control border border-line bg-surface-subtle">
          <summary className="cursor-pointer px-3 py-2 text-sm font-medium">筛选与排序 <span className="ml-2 font-normal text-muted">{hasAppliedQuery ? '已设置条件' : '未设置条件'}</span></summary>
          <div className="border-t border-line p-3" tabIndex={filterDrafts[input.inputId] ? -1 : undefined} aria-invalid={filterDrafts[input.inputId] ? true : undefined}>
            {!boundFields.length ? <p className="mb-2 mt-0 text-sm text-warning">字段筛选和字段排序需要先添加字段映射；状态条件和系统字段排序仍可使用。</p> : null}
            {filterDrafts[input.inputId] ? <p role="alert" className="mb-2 text-sm text-danger">筛选或排序有尚未应用的修改，请先应用或取消。</p> : null}
            <RecordFilterEditor key={`${resetKey}:${input.inputId}`} fields={boundFields} statuses={table.statuses} appliedQuery={{ filter: input.filter as unknown as FilterExpression, orderBy: input.orderBy as unknown as OrderBy[] }} disabled={disabled} onDirtyChange={dirty => setFilterDrafts(current => current[input.inputId] === dirty ? current : { ...current, [input.inputId]: dirty })} onApply={(query: RecordQuery) => replace(index, { ...input, filter: query.filter as unknown as InputDefinition['filter'], orderBy: query.orderBy as unknown as InputDefinition['orderBy'] })}/>
          </div>
        </details> : null}
      </article>
    })}
  </section>
}
