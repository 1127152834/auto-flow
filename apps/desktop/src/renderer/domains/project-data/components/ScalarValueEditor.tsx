import { useEffect, useState } from 'react'
import { FormField } from '../../../shared/components/FormField'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Textarea } from '../../../shared/components/ui/textarea'
import type { ScalarDraft, ScalarDraftControl } from '../scalar-draft'

export type ScalarValueEditorProps = {
  id: string
  label: string
  type: 'string' | 'number' | 'boolean' | 'date'
  draft: ScalarDraft
  onChange(draft: ScalarDraft): void
  disabled?: boolean
  readOnly?: boolean
  allowMissing?: boolean
  error?: string
  errorTarget?: ScalarDraftControl
  compact?: boolean
  presenceDisplay?: 'always' | 'contextual'
}

export function ScalarValueEditor({ id, label, type, draft, onChange, disabled = false, readOnly = false, allowMissing = false, error, errorTarget, compact = false, presenceDisplay = 'always' }: ScalarValueEditorProps) {
  const update = (change: Partial<ScalarDraft>) => onChange({ ...draft, ...change })
  const hasLineBreak = /[\r\n]/.test(draft.text)
  const [multiline, setMultiline] = useState(hasLineBreak)
  const [showPresence, setShowPresence] = useState(false)
  useEffect(() => { if (hasLineBreak) setMultiline(true) }, [hasLineBreak])
  const presenceOptions = [
    ...(allowMissing ? [{ value: 'missing', label: '不填写' }] : draft.presence === 'missing' ? [{ value: 'missing', label: '未填写', disabled: true }] : []),
    { value: 'null', label: '清空' },
    { value: 'value', label: '填写值' },
  ]
  return <fieldset className={`grid min-w-0 ${compact ? 'gap-2' : 'gap-3'}`}>
    <legend className={compact ? 'sr-only' : 'mb-1 text-sm font-medium text-ink'}>{label}</legend>
    {presenceDisplay === 'always' || draft.presence !== 'value' || readOnly || showPresence ? <FormField label="值状态" htmlFor={`${id}-presence`} error={errorTarget === 'presence' ? error : undefined}>
      <Select aria-label={`${label}值状态`} value={draft.presence} options={presenceOptions} disabled={disabled} readOnly={readOnly} clearable={false}
        onValueChange={value => { if (value) update({ presence: value as ScalarDraft['presence'] }) }} />
    </FormField> : <Button size="sm" variant="ghost" onClick={() => setShowPresence(true)}>值选项</Button>}
    {draft.presence === 'value' && type === 'string' ? <FormField label={label} htmlFor={id} error={errorTarget === 'value' ? error : undefined}>
      {compact && !multiline ? <Input size="sm" value={draft.text} disabled={disabled} readOnly={readOnly} onChange={event => update({ text: event.target.value })} /> : <Textarea rows={compact ? 2 : undefined} className={compact ? 'min-h-0' : undefined} value={draft.text} disabled={disabled} readOnly={readOnly} onChange={event => update({ text: event.target.value })} />}
    </FormField> : null}
    {compact && draft.presence === 'value' && type === 'string' ? <Button size="sm" variant="ghost" disabled={disabled || readOnly || (multiline && hasLineBreak)} onClick={() => setMultiline(value => !value)}>{multiline ? '使用单行输入' : '使用多行输入'}</Button> : null}
    {draft.presence === 'value' && type === 'number' ? <FormField label={label} htmlFor={id} error={errorTarget === 'value' ? error : undefined}>
      <Input inputMode="decimal" value={draft.text} disabled={disabled} readOnly={readOnly} onChange={event => update({ text: event.target.value })} />
    </FormField> : null}
    {draft.presence === 'value' && type === 'boolean' ? <FormField label={label} htmlFor={id} error={errorTarget === 'value' ? error : undefined}>
      <Select aria-label={label} value={draft.boolean ? 'true' : 'false'} options={[{ value: 'true', label: '是' }, { value: 'false', label: '否' }]}
        disabled={disabled} readOnly={readOnly} clearable={false} onValueChange={value => { if (value) update({ boolean: value === 'true' }) }} />
    </FormField> : null}
    {draft.presence === 'value' && type === 'date' ? <>
      <FormField label="精度" htmlFor={`${id}-precision`}><Select aria-label={`${label}精度`} value={draft.precision} options={[{ value: 'date', label: '日期' }, { value: 'datetime', label: '日期时间' }]}
        disabled={disabled} readOnly={readOnly} clearable={false} onValueChange={value => { if (value) update({ precision: value as ScalarDraft['precision'], ...(value === 'date' ? { offset: '' } : {}) }) }} /></FormField>
      <FormField label={label} htmlFor={id} error={errorTarget === 'value' ? error : undefined}><Input value={draft.text} disabled={disabled} readOnly={readOnly} placeholder={draft.precision === 'date' ? 'YYYY-MM-DD' : 'YYYY-MM-DDTHH:mm:ss'} onChange={event => update({ text: event.target.value })} /></FormField>
      {draft.precision === 'datetime' ? <FormField label="时区偏移" htmlFor={`${id}-offset`} hint="留空、Z 或 ±HH:MM" error={errorTarget === 'offset' ? error : undefined}><Input aria-label={`${label}时区偏移`} value={draft.offset} disabled={disabled} readOnly={readOnly} placeholder="+08:00" onChange={event => update({ offset: event.target.value })} /></FormField> : null}
    </> : null}
  </fieldset>
}
