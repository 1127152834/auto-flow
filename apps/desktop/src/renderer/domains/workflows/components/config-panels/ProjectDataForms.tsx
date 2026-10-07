import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import type { components } from '../../../../shared/api/generated'
import { coerceValue, conditionsFromFilter, filterFromConditions, isNullOperator, recordFromRows, rowsFromRecord, valueText } from '../../lib/projectDataForm'
import { SelectNative as Select } from '../controls/select-native'
import { VariableInput } from '../controls/variable-input'

type Field = components['schemas']['DataFieldView']

const operatorLabels: Record<string, string> = { eq: '等于', neq: '不等于', contains: '包含', startsWith: '开头是', gt: '大于', gte: '大于等于', lt: '小于', lte: '小于等于', isNull: '为空', isNotNull: '不为空' }
const operatorsByType: Record<string, string[]> = {
  string: ['eq', 'neq', 'contains', 'startsWith', 'isNull', 'isNotNull'], number: ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'isNull', 'isNotNull'],
  boolean: ['eq', 'neq', 'isNull', 'isNotNull'], date: ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'isNull', 'isNotNull'],
}

function FieldSelect({ label, fields, value, onChange, taken = [] }: { label: string; fields: Field[]; value: string; onChange(fieldId: string): void; taken?: string[] }) {
  const missing = value && !fields.some(field => field.ref.fieldId === value)
  return <Select aria-label={label} value={value} onChange={event => onChange(event.target.value)}>
    <option value="">选择字段</option>{missing ? <option value={value} disabled>字段已失效</option> : null}
    {fields.filter(field => !taken.includes(field.ref.fieldId)).map(field => <option key={field.ref.fieldId} value={field.ref.fieldId}>{field.name}</option>)}
  </Select>
}

/**
 * Rows keep the text the user typed; only the saved value is converted, so "0." is not turned into 0 while typing.
 * When the saved value changes from outside (the advanced editor) the rows are rebuilt from it; our own commits are recognised and left alone.
 */
function useTextRows<Row>(saved: string, fromSaved: () => Row[], toSaved: (rows: Row[]) => string) {
  const [rows, setRows] = useState<Row[]>(fromSaved)
  const [seen, setSeen] = useState(saved)
  if (saved !== seen) { setSeen(saved); if (saved !== toSaved(rows)) setRows(fromSaved()) }
  return [rows, setRows] as const
}

type TextRow = { fieldId: string; text: string }
type TextCondition = TextRow & { operator: string }

/** 字段 = 值 rows for creating or updating a record; values accept variable references. */
export function FieldValueRows({ fields, value, onChange }: { fields: Field[]; value: unknown; onChange(next: Record<string, unknown>): void }) {
  const writable = fields.filter(field => field.writable && !field.formula)
  const typeOf = (fieldId: string) => fields.find(field => field.ref.fieldId === fieldId)?.type
  const record = (rows: TextRow[]) => recordFromRows(rows.map(row => ({ fieldId: row.fieldId, value: coerceValue(typeOf(row.fieldId), row.text) })))
  const [rows, setRows] = useTextRows<TextRow>(JSON.stringify(value ?? {}), () => rowsFromRecord(value).map(row => ({ fieldId: row.fieldId, text: valueText(row.value) })), next => JSON.stringify(record(next)))
  const commit = (next: TextRow[]) => { setRows(next); onChange(record(next)) }
  return <div className="space-y-2">
    {rows.length === 0 && <p className="text-xs text-muted-foreground">还没有要写入的字段，点击下方“添加字段”。</p>}
    {rows.map((row, index) => <div key={index} className="grid grid-cols-[1fr_1fr_auto] items-center gap-2">
      <FieldSelect label={`写入字段 ${index + 1}`} fields={writable} value={row.fieldId} taken={rows.filter((_, i) => i !== index).map(item => item.fieldId)} onChange={fieldId => commit(rows.map((item, i) => i === index ? { ...item, fieldId } : item))} />
      <VariableInput aria-label={`写入值 ${index + 1}`} value={row.text} placeholder="填写内容，或输入 { 引用变量" onChange={text => commit(rows.map((item, i) => i === index ? { ...item, text } : item))} />
      <button type="button" aria-label={`删除写入字段 ${index + 1}`} onClick={() => commit(rows.filter((_, i) => i !== index))}><Trash2 className="size-4" /></button>
    </div>)}
    <button type="button" className="flex items-center gap-1 text-sm" onClick={() => setRows([...rows, { fieldId: '', text: '' }])}><Plus className="size-4" />添加字段</button>
  </div>
}

/** 字段 / 比较 / 值 rows for 查询记录. A stored filter that is richer than "all of these" is kept as is. */
export function ConditionRows({ fields, filter, onChange }: { fields: Field[]; filter: unknown; onChange(next: Record<string, unknown> | null): void }) {
  const typeOf = (fieldId: string) => fields.find(field => field.ref.fieldId === fieldId)?.type ?? 'string'
  const built = (rows: TextCondition[]) => filterFromConditions(rows.map(row => ({ fieldId: row.fieldId, operator: row.operator, value: coerceValue(typeOf(row.fieldId), row.text) })))
  const [rows, setRows] = useTextRows<TextCondition>(JSON.stringify(filter ?? null), () => (conditionsFromFilter(filter) ?? []).map(item => ({ fieldId: item.fieldId, operator: item.operator, text: valueText(item.value) })), next => JSON.stringify(built(next)))
  if (conditionsFromFilter(filter) === null) return <p className="text-xs text-muted-foreground">已有的查询条件包含多层或状态条件，这里不能逐行编辑；可在“高级”中查看和修改。</p>
  const commit = (next: TextCondition[]) => { setRows(next); onChange(built(next)) }
  return <div className="space-y-2">
    {rows.length === 0 && <p className="text-xs text-muted-foreground">没有条件时返回全部记录。</p>}
    {rows.map((row, index) => <div key={index} className="grid grid-cols-[1fr_auto] items-center gap-2">
      <div className="grid grid-cols-3 gap-2">
        <FieldSelect label={`条件字段 ${index + 1}`} fields={fields} value={row.fieldId} onChange={fieldId => commit(rows.map((item, i) => i === index ? { fieldId, operator: 'eq', text: '' } : item))} />
        <Select aria-label={`比较方式 ${index + 1}`} value={row.operator} onChange={event => commit(rows.map((item, i) => i === index ? { ...item, operator: event.target.value } : item))}>
          {(operatorsByType[typeOf(row.fieldId)] ?? operatorsByType.string).map(operator => <option key={operator} value={operator}>{operatorLabels[operator]}</option>)}
        </Select>
        {isNullOperator(row.operator) ? <span /> : <VariableInput aria-label={`比较值 ${index + 1}`} value={row.text} placeholder="填写内容，或输入 { 引用变量" onChange={text => commit(rows.map((item, i) => i === index ? { ...item, text } : item))} />}
      </div>
      <button type="button" aria-label={`删除条件 ${index + 1}`} onClick={() => commit(rows.filter((_, i) => i !== index))}><Trash2 className="size-4" /></button>
    </div>)}
    <button type="button" className="flex items-center gap-1 text-sm" onClick={() => setRows([...rows, { fieldId: '', operator: 'eq', text: '' }])}><Plus className="size-4" />添加条件</button>
  </div>
}

export function ReturnFields({ fields, selected, onChange }: { fields: Field[]; selected: string[]; onChange(next: string[]): void }) {
  return <fieldset className="space-y-1"><legend className="text-sm">返回哪些字段</legend>
    {fields.map(field => <label className="flex gap-2" key={field.ref.fieldId}>
      <input type="checkbox" checked={selected.includes(field.ref.fieldId)} onChange={event => onChange(event.target.checked ? [...selected, field.ref.fieldId] : selected.filter(id => id !== field.ref.fieldId))} />{field.name}
    </label>)}
  </fieldset>
}
