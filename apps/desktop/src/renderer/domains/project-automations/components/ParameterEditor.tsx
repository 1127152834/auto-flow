import { useEffect, useRef, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Switch } from '../../../shared/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import type { DraftState, FieldErrors, JsonScalar, ParameterDefinition } from './policy-types'

export type ParameterEditorProps = {
  value: ParameterDefinition[]
  onChange(value: ParameterDefinition[]): void
  disabled?: boolean
  errors?: FieldErrors
  resetKey?: string | number
  onDraftStateChange?(state: DraftState): void
}

const validNumberDraft = (draft: string) => draft.trim() !== '' && Number.isFinite(Number(draft))
const hasDefault = (parameter: ParameterDefinition) => Object.hasOwn(parameter, 'defaultValue')
const typeOptions = [
  { value: 'string', label: '文本' },
  { value: 'number', label: '数字' },
  { value: 'boolean', label: '布尔' },
] as const
const booleanOptions = [
  { value: 'omitted', label: '未提供' },
  { value: 'true', label: '开启' },
  { value: 'false', label: '关闭' },
  { value: 'null', label: '空值' },
]

const matchesType = (parameter: ParameterDefinition) => !hasDefault(parameter) || parameter.defaultValue === null || typeof parameter.defaultValue === parameter.type

export function ParameterEditor({ value, onChange, disabled = false, errors = {}, resetKey, onDraftStateChange }: ParameterEditorProps) {
  const [numberDrafts, setNumberDrafts] = useState<Record<string, string>>({})
  const controlledDefaults = new Map(value.map(parameter => [parameter.parameterId, `${parameter.type}:${JSON.stringify(parameter.defaultValue)}`]))
  const previousDefaults = useRef(controlledDefaults)
  const pendingDefaults = useRef(new Map<string, number>())
  useEffect(() => {
    const previous = previousDefaults.current
    previousDefaults.current = controlledDefaults
    const retained = new Set<string>()
    for (const parameter of value) {
      const id = parameter.parameterId
      if (controlledDefaults.get(id) === previous.get(id)
        || (parameter.type === 'number' && parameter.defaultValue === pendingDefaults.current.get(id))) retained.add(id)
      if (controlledDefaults.get(id) !== previous.get(id)) pendingDefaults.current.delete(id)
    }
    // Capture the decision before the updater: React may replay state updaters.
    setNumberDrafts(current => Object.fromEntries(Object.entries(current).filter(([id]) => retained.has(id))))
  }, [value])
  useEffect(() => {
    pendingDefaults.current.clear()
    setNumberDrafts({})
  }, [resetKey]) // resetKey is the explicit parent reset boundary.
  const draftDirty = Object.keys(numberDrafts).length > 0
  const draftValid = Object.values(numberDrafts).every(validNumberDraft) && value.every(matchesType) && !Object.values(errors).some(Boolean)
  const draftCallback = useRef(onDraftStateChange), lastDraftState = useRef<DraftState | undefined>(undefined)
  useEffect(() => { draftCallback.current = onDraftStateChange }, [onDraftStateChange])
  useEffect(() => {
    if (lastDraftState.current?.dirty === draftDirty && lastDraftState.current.valid === draftValid) return
    lastDraftState.current = { dirty: draftDirty, valid: draftValid }
    draftCallback.current?.(lastDraftState.current)
  }, [draftDirty, draftValid])

  const replace = (index: number, patch: Partial<ParameterDefinition>) => onChange(value.map((parameter, itemIndex) => itemIndex === index ? { ...parameter, ...patch } : parameter))
  const setDefault = (index: number, defaultValue: JsonScalar | undefined) => {
    const parameter = value[index]
    const next = { ...parameter }
    if (defaultValue === undefined) delete next.defaultValue
    else next.defaultValue = defaultValue
    onChange(value.map((item, itemIndex) => itemIndex === index ? next : item))
  }
  const clearNumberDraft = (parameterId: string) => setNumberDrafts(current => { const next = { ...current }; delete next[parameterId]; return next })
  const setType = (index: number, type: ParameterDefinition['type']) => {
    clearNumberDraft(value[index].parameterId)
    replace(index, { type })
  }
  const move = (index: number, offset: number) => {
    const next = [...value], target = index + offset
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange(next)
  }

  return <section className="grid gap-3">
    <div className="flex items-center justify-between gap-3">
      <h3 className="m-0 text-base font-semibold">启动参数</h3>
      <Button size="sm" disabled={disabled} onClick={() => onChange([...value, { parameterId: crypto.randomUUID(), name: '', type: 'string', required: false }])}>新增参数</Button>
    </div>
    <TableScroll label="启动参数列表" className="rounded-control border border-line">
      <Table aria-label="启动参数" className="min-w-[760px] table-fixed">
        <TableHeader><TableRow>
          <TableHead className="w-[18%]">参数名称</TableHead><TableHead className="w-[13%]">类型</TableHead><TableHead className="w-[8%]">必填</TableHead><TableHead className="w-[24%]">默认值</TableHead><TableHead className="w-[20%]">说明</TableHead><TableHead>操作</TableHead>
        </TableRow></TableHeader>
        <TableBody>{value.length ? value.map((parameter, index) => {
          const nameError = errors[`${parameter.parameterId}.name`]
          const defaultError = errors[`${parameter.parameterId}.defaultValue`]
          const draft = numberDrafts[parameter.parameterId]
          const draftInvalid = draft !== undefined && !validNumberDraft(draft)
          const typeError = !matchesType(parameter) ? '默认值类型与参数类型不一致，请修正或清除' : undefined
          const nameErrorId = `parameter-${parameter.parameterId}-name-error`
          const defaultErrorId = `parameter-${parameter.parameterId}-default-error`
          return <TableRow key={parameter.parameterId}>
            <TableCell><Input size="sm" aria-label={`参数名称 ${parameter.name}`} value={parameter.name} disabled={disabled} aria-invalid={Boolean(nameError)} aria-describedby={nameError ? nameErrorId : undefined} onChange={event => replace(index, { name: event.target.value })}/>{nameError ? <p id={nameErrorId} role="alert" className="mt-1 text-xs text-danger">{nameError}</p> : null}</TableCell>
            <TableCell><Select size="sm" aria-label={`参数类型 ${parameter.name}`} value={parameter.type} options={typeOptions} clearable={false} disabled={disabled} onValueChange={type => {
              if (!type) return
              setNumberDrafts(current => { const next = { ...current }; delete next[parameter.parameterId]; return next })
              setType(index, type as ParameterDefinition['type'])
            }}/></TableCell>
            <TableCell><Switch aria-label={`必填参数 ${parameter.name}`} checked={parameter.required} disabled={disabled} onCheckedChange={required => replace(index, { required })}/></TableCell>
            <TableCell>{parameter.type === 'boolean'
              ? <Select size="sm" aria-label={`默认值 ${parameter.name}`} value={!hasDefault(parameter) ? 'omitted' : parameter.defaultValue === null ? 'null' : typeof parameter.defaultValue === 'boolean' ? String(parameter.defaultValue) : 'mismatch'} options={booleanOptions} clearable={false} disabled={disabled} errorMessage={defaultError ?? typeError} onValueChange={choice => { clearNumberDraft(parameter.parameterId); setDefault(index, choice === 'omitted' ? undefined : choice === 'null' ? null : choice === 'true') }}/>
              : <div className="grid gap-1"><Input size="sm" aria-label={`默认值 ${parameter.name}`} data-default-presence={!hasDefault(parameter) ? 'omitted' : parameter.defaultValue === null ? 'null' : 'provided'} value={parameter.type === 'number' && draft !== undefined ? draft : parameter.defaultValue == null ? '' : String(parameter.defaultValue)} disabled={disabled} aria-invalid={Boolean(defaultError || draftInvalid || typeError)} aria-describedby={defaultError || draftInvalid || typeError ? defaultErrorId : undefined} onChange={event => {
                const text = event.target.value
                if (parameter.type === 'string') { setDefault(index, text); return }
                const parsed = Number(text)
                setNumberDrafts(current => ({ ...current, [parameter.parameterId]: text }))
                if (text.trim() && Number.isFinite(parsed)) { pendingDefaults.current.set(parameter.parameterId, parsed); setDefault(index, parsed) }
              }} onBlur={() => { if (draft !== undefined && draft.trim() && Number.isFinite(Number(draft))) clearNumberDraft(parameter.parameterId) }}/>
                {draftInvalid || defaultError || typeError ? <p id={defaultErrorId} role="alert" className="text-xs text-danger">{draftInvalid ? '请输入有效数字' : defaultError ?? typeError}</p> : null}
                <div className="flex gap-1"><Button size="sm" variant="ghost" disabled={disabled || !hasDefault(parameter)} onClick={() => { clearNumberDraft(parameter.parameterId); setDefault(index, undefined) }}>不提供</Button><Button size="sm" variant="ghost" disabled={disabled} onClick={() => { clearNumberDraft(parameter.parameterId); setDefault(index, null) }}>设为空值</Button></div>
              </div>}
            </TableCell>
            <TableCell><Input size="sm" aria-label={`参数说明 ${parameter.name}`} aria-describedby={errors[`${parameter.parameterId}.description`] ? `parameter-${parameter.parameterId}-description-error` : undefined} value={parameter.description ?? ''} disabled={disabled} aria-invalid={Boolean(errors[`${parameter.parameterId}.description`])} onChange={event => replace(index, { description: event.target.value })}/>{errors[`${parameter.parameterId}.description`] ? <p id={`parameter-${parameter.parameterId}-description-error`} role="alert" className="text-xs text-danger">{errors[`${parameter.parameterId}.description`]}</p> : null}</TableCell>
            <TableCell><div className="flex flex-wrap gap-1">
              <Button size="sm" variant="ghost" aria-label={`上移参数 ${parameter.name}`} disabled={disabled || index === 0} onClick={() => move(index, -1)}>上移</Button>
              <Button size="sm" variant="ghost" aria-label={`下移参数 ${parameter.name}`} disabled={disabled || index === value.length - 1} onClick={() => move(index, 1)}>下移</Button>
              <Button size="sm" variant="ghost" aria-label={`移除参数 ${parameter.name}`} disabled={disabled} onClick={() => onChange(value.filter((_, itemIndex) => itemIndex !== index))}>移除</Button>
            </div></TableCell>
          </TableRow>
        }) : <TableRow><TableCell colSpan={6} className="py-8 text-center text-muted">尚未设置启动参数</TableCell></TableRow>}</TableBody>
      </Table>
    </TableScroll>
    <p className="m-0 text-xs text-muted">参数名称可以修改，参数身份保持不变；必填参数可以在启动时填写。</p>
  </section>
}
