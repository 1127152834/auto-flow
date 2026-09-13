import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Checkbox } from '../../../shared/components/ui/checkbox'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { fieldFormSchema } from '../field-form-schema'

type Sheet = components['schemas']['ExcelSheetInspection']
type Field = components['schemas']['DataFieldView']
type FieldWrite = components['schemas']['DataFieldWrite']
type Mapping = components['schemas']['ExcelMapping']
type Identity = components['schemas']['SystemExcelIdentity'] | components['schemas']['ColumnExcelIdentity']
export type ExcelImportMappingDraft = { columns: Array<Mapping | { columnIndex: number; target: null }>; identity: Identity }
export type ExcelImportMappingProps = {
  sheet: Sheet; mode: 'create' | 'replace'; existingFields?: Field[]; value: ExcelImportMappingDraft
  disabled?: boolean; onChange(value: ExcelImportMappingDraft): void; onContinue(value: { mapping: Mapping[]; identity: Identity }): void
}

export const createExcelImportMappingDraft = (sheet: Sheet): ExcelImportMappingDraft => ({
  columns: sheet.headers.map((name, columnIndex) => ({ columnIndex, target: { kind: 'new', definition: { key: `column_${columnIndex + 1}`, name, type: 'string', required: false, validation: {} } } })),
  identity: { mode: 'system' },
})

const cellText = (value: Sheet['sample'][number][number]) => value == null ? '' : typeof value === 'object' ? value.value : String(value)
const errorsFor = (value: ExcelImportMappingDraft) => {
  const errors: string[] = [], targets = new Set<string>(), keys = new Set<string>()
  for (const column of value.columns) {
    if (column.target?.kind === 'existing') {
      if (targets.has(column.target.fieldId)) errors.push('同一个现有字段不能映射多列。')
      targets.add(column.target.fieldId)
    }
    if (column.target?.kind === 'new') {
      const field = column.target.definition, key = field.key.trim()
      const result = fieldFormSchema.safeParse({ key: field.key, name: field.name, type: field.type, required: field.required, minLength: String(field.validation.minLength ?? ''), maxLength: String(field.validation.maxLength ?? ''), pattern: String(field.validation.pattern ?? ''), minimum: String(field.validation.minimum ?? ''), maximum: String(field.validation.maximum ?? '') })
      if (!result.success) errors.push(`第 ${column.columnIndex + 1} 列的新字段定义或约束无效。`)
      if (keys.has(key)) errors.push('新字段键不能重复。')
      keys.add(key)
    }
  }
  if (!value.columns.some(column => column.target !== null)) errors.push('至少映射一列后才能继续。')
  if (value.identity.mode === 'column' && !value.columns[value.identity.columnIndex]?.target) errors.push('身份列不能忽略；请先将该列映射到字段。')
  return [...new Set(errors)]
}

export function ExcelImportMapping({ sheet, mode, existingFields = [], value, disabled, onChange, onContinue }: ExcelImportMappingProps) {
  const update = (columnIndex: number, column: ExcelImportMappingDraft['columns'][number]) => onChange({ ...value, columns: value.columns.map((current, index) => index === columnIndex ? column : current) })
  const errors = errorsFor(value)
  const mappingOptions = [{ value: 'ignore', label: '忽略此列' }, { value: 'new', label: '新增字段' }, ...(mode === 'replace' ? existingFields.filter(field => field.writable && !field.formula).map(field => ({ value: `existing:${field.ref.fieldId}`, label: `现有字段：${field.name}`, description: field.key })) : [])]
  const constraint = (columnIndex: number, definition: FieldWrite, key: string, raw: string, numeric = false) => {
    const validation = { ...definition.validation }
    if (raw === '') delete validation[key]
    else validation[key] = numeric ? Number(raw) : raw
    update(columnIndex, { columnIndex, target: { kind: 'new', definition: { ...definition, validation } } })
  }
  return <section className="grid min-w-0 gap-4" aria-label="Excel 字段与身份映射">
    <div><h3 className="font-medium">字段映射</h3><p className="text-sm text-muted">样例只用于确认列内容；实际提交会验证全部 {sheet.rowCount} 行。标题相同不会自动复用现有字段。</p></div>
    <label className="grid gap-2 text-sm">记录身份<Select aria-label="记录身份" value={value.identity.mode === 'system' ? 'system' : `column:${value.identity.columnIndex}`} clearable={false} disabled={disabled} options={[{ value: 'system', label: '系统生成身份' }, ...sheet.headers.map((header, index) => ({ value: `column:${index}`, label: `${header || `第 ${index + 1} 列`}${sheet.identityCandidates.includes(index) ? '（候选）' : ''}`, disabled: !sheet.identityCandidates.includes(index) }))]} onValueChange={choice => onChange({ ...value, identity: choice === 'system' || choice == null ? { mode: 'system' } : { mode: 'column', columnIndex: Number(choice.slice(7)) } })} /><span className="text-xs text-muted">候选表示列类型可用于身份且不含公式；提交时仍会验证全部身份值非空且唯一。</span></label>
    <div className="grid max-h-[34rem] min-w-0 gap-3 overflow-auto pr-1">
      {sheet.headers.map((header, index) => {
        const column = value.columns[index] ?? { columnIndex: index, target: null }
        const definition = column.target?.kind === 'new' ? column.target.definition : null
        const updateDefinition = (next: FieldWrite) => update(index, { columnIndex: index, target: { kind: 'new', definition: next } })
        const selected = column.target?.kind === 'existing' ? `existing:${column.target.fieldId}` : column.target?.kind ?? 'ignore'
        return <fieldset className="grid min-w-0 gap-3 rounded-control border border-line p-3" key={index}><legend className="max-w-full truncate px-1 font-medium" title={header}>{header || `第 ${index + 1} 列`}</legend>
          <p className="truncate text-xs text-muted" title={cellText(sheet.sample[0]?.[index] ?? null)}>样例：{cellText(sheet.sample[0]?.[index] ?? null) || '空'}</p>
          <Select aria-label="列映射" value={selected} options={mappingOptions.map(option => option.value === 'ignore' && value.identity.mode === 'column' && value.identity.columnIndex === index ? { ...option, disabled: true } : option)} clearable={false} disabled={disabled} onValueChange={choice => {
            if (choice === 'ignore') update(index, { columnIndex: index, target: null })
            else if (choice?.startsWith('existing:')) update(index, { columnIndex: index, target: { kind: 'existing', fieldId: choice.slice(9) } })
            else update(index, { columnIndex: index, target: { kind: 'new', definition: column.target?.kind === 'new' ? column.target.definition : { key: `column_${index + 1}`, name: header, type: 'string', required: false, validation: {} } } })
          }} />
          {value.identity.mode === 'column' && value.identity.columnIndex === index ? <p className="text-xs text-muted">身份列必须保持字段映射，不能忽略。</p> : null}
          {definition ? <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-xs">字段键<Input aria-label="字段键" value={definition.key} disabled={disabled} onChange={event => updateDefinition({ ...definition, key: event.target.value })} /></label>
            <label className="grid gap-1 text-xs">字段名称<Input aria-label="字段名称" value={definition.name} disabled={disabled} onChange={event => updateDefinition({ ...definition, name: event.target.value })} /></label>
            <label className="grid gap-1 text-xs">字段类型<Select aria-label="字段类型" value={definition.type} clearable={false} disabled={disabled} options={['string', 'number', 'boolean', 'date'].map(type => ({ value: type, label: ({ string: '文本', number: '数字', boolean: '布尔', date: '日期' } as Record<string, string>)[type] }))} onValueChange={type => type && updateDefinition({ ...definition, type: type as FieldWrite['type'], validation: {} })} /></label>
            <label className="flex items-center gap-2 self-end text-sm"><Checkbox aria-label="必填" checked={definition.required} disabled={disabled} onCheckedChange={checked => updateDefinition({ ...definition, required: checked === true })} />必填</label>
            {definition.type === 'string' ? <><label className="grid gap-1 text-xs">最小长度<Input aria-label="最小长度" type="number" min="0" value={String(definition.validation.minLength ?? '')} disabled={disabled} onChange={event => constraint(index, definition, 'minLength', event.target.value, true)} /></label><label className="grid gap-1 text-xs">最大长度<Input aria-label="最大长度" type="number" min="0" value={String(definition.validation.maxLength ?? '')} disabled={disabled} onChange={event => constraint(index, definition, 'maxLength', event.target.value, true)} /></label><label className="grid gap-1 text-xs sm:col-span-2">匹配规则<Input aria-label="匹配规则" value={String(definition.validation.pattern ?? '')} disabled={disabled} onChange={event => constraint(index, definition, 'pattern', event.target.value)} /></label></> : null}
            {definition.type === 'number' ? <><label className="grid gap-1 text-xs">最小值<Input aria-label="最小值" inputMode="decimal" value={String(definition.validation.minimum ?? '')} disabled={disabled} onChange={event => constraint(index, definition, 'minimum', event.target.value, true)} /></label><label className="grid gap-1 text-xs">最大值<Input aria-label="最大值" inputMode="decimal" value={String(definition.validation.maximum ?? '')} disabled={disabled} onChange={event => constraint(index, definition, 'maximum', event.target.value, true)} /></label></> : null}
          </div> : null}
        </fieldset>
      })}
    </div>
    {errors.map(error => <p role="alert" className="text-sm text-danger" key={error}>{error}</p>)}
    <Button variant="primary" disabled={disabled || errors.length > 0} onClick={() => onContinue({ mapping: value.columns.filter((column): column is Mapping => column.target !== null), identity: value.identity })}>继续导入</Button>
  </section>
}
