import { useEffect, useRef, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'
import type { components } from '../../../shared/api/generated'
import type { InputMatchFetcher } from '../input-match-api'
import { useInputMatch } from '../use-input-match'
import { FieldBindingSection } from './input-plan/FieldBindingSection'
import { InputConditionSection } from './input-plan/InputConditionSection'
import { InputMatchPreview, InputMatchStatus } from './input-plan/InputMatchPreview'
import { InputRelationSection } from './input-plan/InputRelationSection'
import { emptyFilter, InputSourceSection } from './input-plan/InputSourceSection'
import { RelationGraph } from './input-plan/RelationGraph'
import { relationCapabilities as relationCapabilitiesOf } from './input-plan/relations'
import type { InputDefinition, InputTableOption, Plan } from './input-plan/types'

export type { InputTableOption } from './input-plan/types'

export type InputPlanEditorProps = {
  value: Plan
  onChange(value: Plan): void
  tables: InputTableOption[]
  disabled?: boolean
  errors?: Record<string, string | undefined>
  resetKey?: string
  onDraftStateChange?(state: { dirty: boolean; valid: boolean }): void
  onLoadRecords?(tableId: string): void
  /** Remediation M2 R2-18/20: the selected workflow's declared inputs; bindings are chosen against it. */
  signature?: components['schemas']['WorkflowSignature'] | null
  /** Remediation M5 R5-17: pre-checks the draft plan (matched rows and samples); omitted when the automation is not saved yet. */
  matchInputs?: InputMatchFetcher
  /** True for an automation that is not saved yet: the pre-check needs a saved automation, so say so. */
  matchAfterSave?: boolean
}

export function InputPlanEditor({ value, onChange, tables, disabled = false, errors = {}, resetKey = '', onDraftStateChange, onLoadRecords, signature, matchInputs, matchAfterSave = false }: InputPlanEditorProps) {
  const unboundGroups = (signature?.inputs ?? []).filter(item => !value.inputs.some(input => input.signatureInput === item.key))
  const [filterDrafts, setFilterDrafts] = useState<Record<string, boolean>>({})
  const root = useRef<HTMLElement>(null)
  const draftCallback = useRef(onDraftStateChange)
  useEffect(() => { draftCallback.current = onDraftStateChange }, [onDraftStateChange])
  useEffect(() => { setFilterDrafts({}) }, [resetKey])
  const filterDirty = value.inputs.some(input => filterDrafts[input.inputId])
  useEffect(() => { draftCallback.current?.({ dirty: filterDirty, valid: !filterDirty }) }, [filterDirty])
  const match = useInputMatch({ fetcher: matchInputs, plan: value })
  // A processing input is kept only while it still names a required input (remediation M2 §2).
  const commit = (inputs: InputDefinition[], chosen = value.processingInputId) => onChange(chosen && inputs.some(input => input.inputId === chosen && input.required) ? { inputs, processingInputId: chosen } : { inputs })
  const replace = (index: number, next: InputDefinition) => commit(value.inputs.map((input, itemIndex) => itemIndex === index ? next : input))
  const requiredInputs = value.inputs.filter(input => input.required)
  const referencedBy = (inputId: string) => value.inputs.find(input => input.mode === 'related' && input.relation?.sourceInputId === inputId)
  const requiredBy = (inputId: string) => value.inputs.find(candidate => {
    if (!candidate.required) return false
    let current: InputDefinition | undefined = candidate
    const visited = new Set<string>()
    while (current?.mode === 'related' && current.relation?.sourceInputId && !visited.has(current.inputId)) {
      visited.add(current.inputId)
      if (current.relation.sourceInputId === inputId) return true
      current = value.inputs.find(item => item.inputId === current?.relation?.sourceInputId)
    }
    return false
  })
  const add = () => {
    const table = tables[0]
    if (!table) return
    commit([...value.inputs, { inputId: crypto.randomUUID(), alias: '', tableId: table.id, datasetGeneration: table.datasetGeneration, mode: 'independent', required: false, fieldBindings: [], filter: emptyFilter(), orderBy: [] }])
  }
  const focusRelation = (inputId: string) => {
    const target = root.current?.querySelector<HTMLElement>(`[data-relation-editor="${CSS.escape(inputId)}"]`)
    target?.scrollIntoView?.({ block: 'center' })
    target?.focus()
  }
  const context = { tables, inputs: value.inputs }
  return <section ref={root} className="grid gap-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="m-0 text-base font-semibold">项目数据输入</h3><p className="mt-1 text-sm text-muted">{value.inputs.length ? '启动前会重新检查完整输入组并原子领取。' : '当前自动化不读取项目数据，可以直接使用参数启动。'}</p></div><Button size="sm" disabled={disabled || !tables.length} onClick={add}>添加数据输入</Button></div>
    {requiredInputs.length > 1 ? <div className="grid gap-2 rounded-control border border-line bg-surface-subtle p-3"><p className="m-0 text-sm text-muted">有多份必填数据，请选择批量运行时逐行处理哪一份；其他数据只作参考，不会被逐行消耗。</p><Select className="max-w-sm" aria-label="逐行处理的数据" value={value.processingInputId ?? null} options={requiredInputs.map(input => ({ value: input.inputId, label: input.alias || '未命名输入', disabled: false }))} clearable={false} disabled={disabled} errorMessage={errors.processingInputId} onValueChange={inputId => { if (inputId) commit(value.inputs, inputId) }}/></div> : null}
    {unboundGroups.length ? <p role="status" className="m-0 text-sm text-warning">工作流需要的流程输入还没有绑定数据：{unboundGroups.map(item => item.name).join('、')}</p> : null}
    <RelationGraph inputs={value.inputs} tables={tables} onSelect={focusRelation}/>
    {matchInputs ? <InputMatchStatus state={match}/> : matchAfterSave && value.inputs.length ? <p className="m-0 text-xs text-muted">保存后可查看当前条件匹配的行数。</p> : null}
    {value.inputs.map((input, index) => {
      const table = tables.find(item => item.id === input.tableId)
      const group = signature?.inputs.find(item => item.key === input.signatureInput)
      const inputErrors = Object.entries(errors).filter(([path, message]) => path.startsWith(`${input.inputId}.`) && Boolean(message))
      const relatedCandidates = value.inputs.slice(0, index).filter(candidate => Object.values(relationCapabilitiesOf(context, input, candidate)).some(Boolean))
      const change = (next: InputDefinition) => replace(index, next)
      return <article key={input.inputId} className="grid min-w-0 gap-3 rounded-control border border-line bg-surface p-3" tabIndex={inputErrors.length ? -1 : undefined} aria-invalid={inputErrors.length ? true : undefined}>
        {inputErrors.length ? <p role="alert" className="m-0 text-sm text-danger">{inputErrors[0][1]}</p> : null}
        <InputSourceSection input={input} context={context} signature={signature} referencedBy={referencedBy(input.inputId)} requiredBy={!input.required ? requiredBy(input.inputId) : undefined} relatedCandidates={relatedCandidates} disabled={disabled} errors={errors} onChange={change} onRemove={() => commit(value.inputs.filter((_, itemIndex) => itemIndex !== index))} onLoadRecords={onLoadRecords}/>
        {input.mode === 'related' ? <InputRelationSection input={input} index={index} context={context} relatedCandidates={relatedCandidates} disabled={disabled} onChange={change}/> : null}
        <FieldBindingSection input={input} table={table} group={group} disabled={disabled} onChange={change}/>
        {table ? <InputConditionSection input={input} table={table} resetKey={resetKey} draftPending={Boolean(filterDrafts[input.inputId])} disabled={disabled} onDirtyChange={dirty => setFilterDrafts(current => current[input.inputId] === dirty ? current : { ...current, [input.inputId]: dirty })} onChange={change}/> : null}
        {matchInputs ? <InputMatchPreview item={match.items.get(input.inputId)} input={input} table={table} stale={match.status === 'loading'}/> : null}
      </article>
    })}
  </section>
}
