import { useEffect, useRef, useState } from 'react'
import { BracketsCurly, Plus, Trash } from '@phosphor-icons/react'
import { FormField } from '../../../shared/components/FormField'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Textarea } from '../../../shared/components/ui/textarea'
import type { WorkflowVariable } from '../types'

type Props = {
  variables: WorkflowVariable[]
  onChange(next: WorkflowVariable[]): void
  onRename(oldName: string, newName: string): void
  onDelete(name: string): void
  onEditStart?(): void
  onEditEnd?(): void
  disabled?: boolean
}

const variableTypes = [['string', '字符串'], ['number', '数字'], ['boolean', '布尔'], ['array', '列表'], ['object', '对象']] as const
const asText = (value: unknown) => typeof value === 'string' ? value : JSON.stringify(value) ?? ''

function parseValue(raw: string, type: string): unknown {
  if (type === 'string') return raw
  if (type === 'number') return raw.trim() && Number.isFinite(Number(raw)) ? Number(raw) : raw
  if (type === 'boolean') return raw === 'true' ? true : raw === 'false' ? false : raw
  try {
    const value: unknown = JSON.parse(raw)
    if (type === 'array' && Array.isArray(value)) return value
    if (type === 'object' && value !== null && typeof value === 'object' && !Array.isArray(value)) return value
  } catch { /* Incomplete JSON stays in the document until the user finishes it. */ }
  return raw
}

function valueError(variable: WorkflowVariable): string | undefined {
  const { type, value } = variable
  if (type === 'string' && typeof value !== 'string') return '当前初值不是字符串，请编辑为文本。'
  if (type === 'number' && (typeof value !== 'number' || !Number.isFinite(value))) return '请输入有效数字；当前输入会随流程保存。'
  if (type === 'boolean' && typeof value !== 'boolean') return '请选择 true 或 false。'
  if (type === 'array' && !Array.isArray(value)) return '请输入 JSON 列表，例如 [1, 2]；当前输入会随流程保存。'
  if (type === 'object' && (value === null || typeof value !== 'object' || Array.isArray(value))) return '请输入 JSON 对象，例如 {"key":"value"}；当前输入会随流程保存。'
}

export function VariablePanel({ variables, onChange, onRename, onDelete, onEditStart, onEditEnd, disabled = false }: Props) {
  const addVariable = () => {
    let number = 1
    while (variables.some((variable) => variable.name === `variable_${number}`)) number += 1
    onChange([...variables, { name: `variable_${number}`, type: 'string', value: '' }])
  }
  return <section className="space-y-4 p-4" aria-label="流程变量配置">
    <div className="flex items-center justify-between gap-2"><h3 className="text-sm font-semibold text-ink">流程变量 <span className="font-normal text-muted">{variables.length}</span></h3><Button type="button" variant="ghost" className="h-8 px-2" onClick={addVariable} disabled={disabled}><Plus size={15} />添加变量</Button></div>
    <p className="text-xs leading-5 text-muted">设置流程初值。在节点的文本字段中使用 {'{name}'} 或 {'${name}'} 引用。</p>
    {!variables.length ? <div className="grid justify-items-center gap-3 rounded-card border border-dashed border-line px-4 py-10 text-center text-muted"><BracketsCurly size={24} /><p className="text-sm">还没有流程变量</p><p className="text-xs leading-5">添加可在多个节点中重复使用的数据。</p></div> : null}
    {variables.map((variable, index) => <VariableRow
      key={variable.name}
      variable={variable}
      names={variables.map((item) => item.name)}
      disabled={disabled}
      onChange={(next) => onChange(variables.map((item, itemIndex) => itemIndex === index ? next : item))}
      onRename={(next) => onRename(variable.name, next)}
      onDelete={() => onDelete(variable.name)}
      onEditStart={onEditStart}
      onEditEnd={onEditEnd}
    />)}
  </section>
}

function VariableRow({ variable, names, onChange, onRename, onDelete, onEditStart, onEditEnd, disabled }: {
  variable: WorkflowVariable
  names: string[]
  onChange(next: WorkflowVariable): void
  onRename(next: string): void
  onDelete(): void
  onEditStart?: () => void
  onEditEnd?: () => void
  disabled: boolean
}) {
  const [name, setName] = useState(variable.name)
  const [raw, setRaw] = useState(() => asText(variable.value))
  const lastValue = useRef(variable.value)
  useEffect(() => {
    if (lastValue.current !== variable.value) {
      lastValue.current = variable.value
      setRaw(asText(variable.value))
    }
  }, [variable.value])
  const nextName = name.trim()
  const nameError = !nextName ? '变量名不能为空。' : !/^[\p{L}_][\p{L}\p{N}_]*$/u.test(nextName) ? '使用中文、字母、数字和下划线，且不能以数字开头。' : nextName !== variable.name && names.includes(nextName) ? '已存在同名变量，请使用其他名称。' : undefined
  const rename = () => {
    if (!nameError && nextName !== variable.name) onRename(nextName)
    onEditEnd?.()
  }
  const changeValue = (text: string) => {
    setRaw(text)
    const value = parseValue(text, variable.type)
    lastValue.current = value
    onChange({ ...variable, value })
  }
  const initialValueProps = { value: raw, disabled, onFocus: onEditStart, onBlur: onEditEnd, onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => changeValue(event.target.value) }

  return <div className="space-y-3 rounded-card border border-line bg-surface-subtle p-3" aria-label={`变量 ${variable.name}`}>
    <div className="flex items-center justify-between gap-2"><code className="truncate text-xs text-muted">{variable.name}</code><Button type="button" variant="ghost" className="h-7 w-7 px-0" aria-label={`删除变量 ${variable.name}`} onClick={onDelete} disabled={disabled}><Trash size={15} /></Button></div>
    <FormField htmlFor={`variable-${variable.name}-name`} label="变量名" error={nameError ? `${nameError}尚未重命名，原名称仍为 ${variable.name}。` : undefined}><Input value={name} disabled={disabled} onFocus={onEditStart} onChange={(event) => setName(event.target.value)} onBlur={rename} onKeyDown={(event) => { if (event.key === 'Enter') event.currentTarget.blur() }} /></FormField>
    <FormField htmlFor={`variable-${variable.name}-type`} label="类型"><Select className="w-full" value={variable.type} disabled={disabled} onChange={(event) => onChange({ ...variable, type: event.target.value as WorkflowVariable['type'] })}>{variableTypes.map(([type, label]) => <option key={type} value={type}>{label}</option>)}</Select></FormField>
    <FormField htmlFor={`variable-${variable.name}-value`} label="初始值" error={valueError(variable)} hint={variable.type === 'array' || variable.type === 'object' ? '使用 JSON 格式；未完成的输入也会保留。' : undefined}>
      {variable.type === 'boolean' ? <Select className="w-full" value={String(variable.value)} disabled={disabled} onChange={(event) => changeValue(event.target.value)}>
        {typeof variable.value !== 'boolean' ? <option value={String(variable.value)}>请选择</option> : null}
        <option value="true">true</option><option value="false">false</option>
      </Select> : variable.type === 'array' || variable.type === 'object' ? <Textarea {...initialValueProps} className="font-mono text-xs" spellCheck={false} /> : <Input {...initialValueProps} inputMode={variable.type === 'number' ? 'decimal' : undefined} />}
    </FormField>
  </div>
}
