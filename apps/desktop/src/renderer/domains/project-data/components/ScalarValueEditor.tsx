import { useEffect, useState } from 'react'
import { Lock, WarningCircle } from '@phosphor-icons/react'
import { FormField } from '../../../shared/components/FormField'
import { Button } from '../../../shared/components/ui/button'
import { CalendarDateInput } from '../../../shared/components/ui/calendar-date-input'
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
  required?: boolean
  helperText?: string
  readOnlyIndicator?: string
}

export function ScalarValueEditor({ id, label, type, draft, onChange, disabled = false, readOnly = false, allowMissing = false, error, errorTarget, compact = false, presentation='dialog', presenceDisplay = 'always', required=false, helperText, readOnlyIndicator }: ScalarValueEditorProps) {
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
  const page=presentation==='page',fieldLabel=page?'':label,fieldClass=page?'[&>label]:sr-only':undefined
  const editingValue=(change:Partial<ScalarDraft>)=>update({...change,presence:'value'})
  const shownText=page&&draft.presence!=='value'?'':draft.text
  const pageState=draft.presence==='missing'?'未填写':draft.presence==='null'?'空值':type==='string'&&draft.text===''?'空字符串':''
  const pageHelp=[pageState,helperText].filter(Boolean).join(' · ')
  const mainError=errorTarget==='value'||errorTarget==='presence'?error:undefined
  const pageInput=type==='string'?<FormField className={fieldClass} label={fieldLabel} htmlFor={id} error={mainError}>{!multiline?<Input aria-label={label} value={shownText} disabled={disabled} readOnly={readOnly} onChange={event=>editingValue({text:event.target.value})}/>:<Textarea aria-label={label} rows={3} className="min-h-20" value={shownText} disabled={disabled} readOnly={readOnly} onChange={event=>editingValue({text:event.target.value})}/>}</FormField>
    :type==='number'?<FormField className={fieldClass} label={fieldLabel} htmlFor={id} error={mainError}><Input aria-label={label} inputMode="decimal" value={shownText} disabled={disabled} readOnly={readOnly} onChange={event=>editingValue({text:event.target.value})}/></FormField>
    :type==='boolean'?<FormField className={fieldClass} label={fieldLabel} htmlFor={id} error={mainError}><Select aria-label={label} value={draft.presence==='value'?(draft.boolean?'true':'false'):null} options={[{value:'true',label:'是'},{value:'false',label:'否'}]} disabled={disabled} readOnly={readOnly} clearable={false} onValueChange={value=>{if(value)editingValue({boolean:value==='true'})}}/></FormField>
    :<><FormField className={fieldClass} label={fieldLabel} htmlFor={id} error={mainError}>{draft.precision==='date'?<CalendarDateInput id={id} aria-label={label} aria-invalid={Boolean(mainError)} value={shownText} disabled={disabled} readOnly={readOnly} onValueChange={value=>editingValue({text:value})}/>:<Input aria-label={label} value={shownText} disabled={disabled} readOnly={readOnly} placeholder="YYYY-MM-DDTHH:mm:ss" onChange={event=>editingValue({text:event.target.value})}/>}</FormField>{draft.precision==='datetime'?<FormField label="时区偏移" htmlFor={`${id}-offset`} hint="留空、Z 或 ±HH:MM" error={errorTarget==='offset'?error:undefined}><Input aria-label={`${label}时区偏移`} value={draft.offset} disabled={disabled} readOnly={readOnly} placeholder="+08:00" onChange={event=>editingValue({offset:event.target.value})}/></FormField>:null}</>
  if(page)return <fieldset className="grid min-w-0 gap-2 [&_input[data-af-control]]:h-11 [&_input[data-af-control]]:text-base [&_button[data-af-control]]:h-11 [&_button[data-af-control]]:text-base [&_textarea[data-af-control]]:min-h-20 [&_textarea[data-af-control]]:text-base">
    <legend className="sr-only">{label}</legend><div data-record-field-layout="page" className="grid min-w-0 items-start gap-3 lg:grid-cols-[250px_minmax(0,1fr)]">
      <span data-record-field-label className="pt-3 text-base font-medium text-ink" aria-hidden="true">{label}{required?<span className="ml-1 text-danger">*</span>:null}{readOnlyIndicator?<span className="ml-2 inline-flex items-center gap-1 text-xs font-normal text-muted"><Lock aria-hidden="true" size={14}/>{readOnlyIndicator}</span>:null}</span>
      <div data-record-field-controls="true" className="grid min-w-0 gap-2 [&_p[role=alert]]:sr-only">{pageInput}{error?<p aria-hidden="true" className="m-0 flex items-center gap-1 text-sm text-danger"><WarningCircle aria-hidden="true" weight="fill" size={17}/>{error}</p>:null}<div data-record-field-help className="flex min-h-6 items-center justify-between gap-3"><p className="m-0 text-sm text-muted">{pageHelp}</p><Button size="sm" variant="ghost" disabled={disabled} onClick={()=>setShowPresence(value=>!value)}>值选项</Button></div>
        {showPresence?<div data-record-field-options className="grid gap-2 rounded-control bg-surface-subtle p-3"><FormField label="值状态" htmlFor={`${id}-presence`} error={errorTarget==='presence'?error:undefined}><Select aria-label={`${label}值状态`} value={draft.presence} options={presenceOptions} disabled={disabled} readOnly={readOnly} clearable={false} onValueChange={value=>{if(value)update({presence:value as ScalarDraft['presence']})}}/></FormField>{type==='string'?<Button className="justify-self-end" size="sm" variant="ghost" disabled={disabled||readOnly||(multiline&&hasLineBreak)} onClick={()=>setMultiline(value=>!value)}>{multiline?'使用单行输入':'使用多行输入'}</Button>:null}{type==='date'?<FormField label="精度" htmlFor={`${id}-precision`}><Select aria-label={`${label}精度`} value={draft.precision} options={[{value:'date',label:'日期'},{value:'datetime',label:'日期时间'}]} disabled={disabled} readOnly={readOnly} clearable={false} onValueChange={value=>{if(value)editingValue({precision:value as ScalarDraft['precision'],...(value==='date'?{offset:''}:{})})}}/></FormField>:null}</div>:null}
      </div>
    </div>
  </fieldset>
  return <fieldset className={`grid min-w-0 ${compact?'gap-2':'gap-3'}`}>
    <legend className={compact?'sr-only':'mb-1 text-sm font-medium text-ink'}>{label}</legend><div className="contents"><div className={`grid min-w-0 ${compact?'gap-2':'gap-3'}`}>
    {presenceDisplay==='always'||draft.presence!=='value'||readOnly||showPresence?<FormField label="值状态" htmlFor={`${id}-presence`} error={errorTarget==='presence'?error:undefined}><Select aria-label={`${label}值状态`} value={draft.presence} options={presenceOptions} disabled={disabled} readOnly={readOnly} clearable={false} onValueChange={value=>{if(value)update({presence:value as ScalarDraft['presence']})}}/></FormField>:<Button size="sm" variant="ghost" onClick={()=>setShowPresence(true)}>值选项</Button>}
    {draft.presence==='value'&&type==='string'?<FormField label={label} htmlFor={id} error={errorTarget==='value'?error:undefined}>{compact&&!multiline?<Input size="sm" value={draft.text} disabled={disabled} readOnly={readOnly} onChange={event=>update({text:event.target.value})}/>:<Textarea rows={compact?2:undefined} className={compact?'min-h-0':undefined} value={draft.text} disabled={disabled} readOnly={readOnly} onChange={event=>update({text:event.target.value})}/>}</FormField>:null}
    {compact&&draft.presence==='value'&&type==='string'?<Button size="sm" variant="ghost" disabled={disabled||readOnly||(multiline&&hasLineBreak)} onClick={()=>setMultiline(value=>!value)}>{multiline?'使用单行输入':'使用多行输入'}</Button>:null}
    {draft.presence==='value'&&type==='number'?<FormField label={label} htmlFor={id} error={errorTarget==='value'?error:undefined}><Input inputMode="decimal" value={draft.text} disabled={disabled} readOnly={readOnly} onChange={event=>update({text:event.target.value})}/></FormField>:null}
    {draft.presence==='value'&&type==='boolean'?<FormField label={label} htmlFor={id} error={errorTarget==='value'?error:undefined}><Select aria-label={label} value={draft.boolean?'true':'false'} options={[{value:'true',label:'是'},{value:'false',label:'否'}]} disabled={disabled} readOnly={readOnly} clearable={false} onValueChange={value=>{if(value)update({boolean:value==='true'})}}/></FormField>:null}
    {draft.presence==='value'&&type==='date'?<><FormField label="精度" htmlFor={`${id}-precision`}><Select aria-label={`${label}精度`} value={draft.precision} options={[{value:'date',label:'日期'},{value:'datetime',label:'日期时间'}]} disabled={disabled} readOnly={readOnly} clearable={false} onValueChange={value=>{if(value)update({precision:value as ScalarDraft['precision'],...(value==='date'?{offset:''}:{})})}}/></FormField><FormField label={label} htmlFor={id} error={errorTarget==='value'?error:undefined}><Input value={draft.text} disabled={disabled} readOnly={readOnly} placeholder={draft.precision==='date'?'YYYY-MM-DD':'YYYY-MM-DDTHH:mm:ss'} onChange={event=>update({text:event.target.value})}/></FormField>{draft.precision==='datetime'?<FormField label="时区偏移" htmlFor={`${id}-offset`} hint="留空、Z 或 ±HH:MM" error={errorTarget==='offset'?error:undefined}><Input aria-label={`${label}时区偏移`} value={draft.offset} disabled={disabled} readOnly={readOnly} placeholder="+08:00" onChange={event=>update({offset:event.target.value})}/></FormField>:null}</>:null}
    </div></div>
  </fieldset>
}
