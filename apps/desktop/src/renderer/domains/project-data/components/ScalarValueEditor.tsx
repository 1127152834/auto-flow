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
  presentation?: 'dialog' | 'page'
  presenceDisplay?: 'always' | 'contextual'
}

export function ScalarValueEditor({ id, label, type, draft, onChange, disabled = false, readOnly = false, allowMissing = false, error, errorTarget, compact = false, presentation='dialog', presenceDisplay = 'always' }: ScalarValueEditorProps) {
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
  const page=presentation==='page',adaptiveText=compact||page,fieldLabel=page?'':label,fieldClass=page?'[&>label]:sr-only':undefined
  return <fieldset className={`grid min-w-0 ${page?'items-start gap-3 sm:grid-cols-[7rem_minmax(0,1fr)]':compact?'gap-2':'gap-3'}`}>
    <legend className={compact ? 'sr-only' : page?'pt-2 text-sm font-medium text-ink':'mb-1 text-sm font-medium text-ink'}>{label}</legend><div className={`grid min-w-0 ${compact?'gap-2':'gap-3'}`}>
    {presenceDisplay === 'always' || draft.presence !== 'value' || readOnly || showPresence ? <FormField label="值状态" htmlFor={`${id}-presence`} error={errorTarget === 'presence' ? error : undefined}>
      <Select aria-label={`${label}值状态`} value={draft.presence} options={presenceOptions} disabled={disabled} readOnly={readOnly} clearable={false}
        onValueChange={value => { if (value) update({ presence: value as ScalarDraft['presence'] }) }} />
    </FormField> : <Button className={page?'justify-self-end':undefined} size="sm" variant="ghost" onClick={() => setShowPresence(true)}>值选项</Button>}
    {draft.presence === 'value' && type === 'string' ? <FormField className={fieldClass} label={fieldLabel} htmlFor={id} error={errorTarget === 'value' ? error : undefined}>
      {adaptiveText && !multiline ? <Input aria-label={page?label:undefined} size={compact?'sm':'md'} value={draft.text} disabled={disabled} readOnly={readOnly} onChange={event => update({ text: event.target.value })} /> : <Textarea aria-label={page?label:undefined} rows={adaptiveText ? page?3:2 : undefined} className={adaptiveText ? 'min-h-0' : undefined} value={draft.text} disabled={disabled} readOnly={readOnly} onChange={event => update({ text: event.target.value })} />}
    </FormField> : null}
    {adaptiveText && draft.presence === 'value' && type === 'string' ? <Button className={page?'justify-self-end':undefined} size="sm" variant="ghost" disabled={disabled || readOnly || (multiline && hasLineBreak)} onClick={() => setMultiline(value => !value)}>{multiline ? '使用单行输入' : '使用多行输入'}</Button> : null}
    {draft.presence === 'value' && type === 'number' ? <FormField className={fieldClass} label={fieldLabel} htmlFor={id} error={errorTarget === 'value' ? error : undefined}>
      <Input aria-label={page?label:undefined} inputMode="decimal" value={draft.text} disabled={disabled} readOnly={readOnly} onChange={event => update({ text: event.target.value })} />
    </FormField> : null}
    {draft.presence === 'value' && type === 'boolean' ? <FormField className={fieldClass} label={fieldLabel} htmlFor={id} error={errorTarget === 'value' ? error : undefined}>
      <Select aria-label={label} value={draft.boolean ? 'true' : 'false'} options={[{ value: 'true', label: '是' }, { value: 'false', label: '否' }]}
        disabled={disabled} readOnly={readOnly} clearable={false} onValueChange={value => { if (value) update({ boolean: value === 'true' }) }} />
    </FormField> : null}
    {draft.presence === 'value' && type === 'date' ? <>
      <FormField label="精度" htmlFor={`${id}-precision`}><Select aria-label={`${label}精度`} value={draft.precision} options={[{ value: 'date', label: '日期' }, { value: 'datetime', label: '日期时间' }]}
        disabled={disabled} readOnly={readOnly} clearable={false} onValueChange={value => { if (value) update({ precision: value as ScalarDraft['precision'], ...(value === 'date' ? { offset: '' } : {}) }) }} /></FormField>
      <FormField className={fieldClass} label={fieldLabel} htmlFor={id} error={errorTarget === 'value' ? error : undefined}><Input aria-label={page?label:undefined} value={draft.text} disabled={disabled} readOnly={readOnly} placeholder={draft.precision === 'date' ? 'YYYY-MM-DD' : 'YYYY-MM-DDTHH:mm:ss'} onChange={event => update({ text: event.target.value })} /></FormField>
      {draft.precision === 'datetime' ? <FormField label="时区偏移" htmlFor={`${id}-offset`} hint="留空、Z 或 ±HH:MM" error={errorTarget === 'offset' ? error : undefined}><Input aria-label={`${label}时区偏移`} value={draft.offset} disabled={disabled} readOnly={readOnly} placeholder="+08:00" onChange={event => update({ offset: event.target.value })} /></FormField> : null}
    </> : null}</div>
  </fieldset>
}
