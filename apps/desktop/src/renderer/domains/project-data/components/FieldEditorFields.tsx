import { Info, Lock } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { useWatch, type UseFormReturn } from 'react-hook-form'
import { FormField } from '../../../shared/components/FormField'
import { Checkbox } from '../../../shared/components/ui/checkbox'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Switch } from '../../../shared/components/ui/switch'
import type { components } from '../../../shared/api/generated'
import type { FieldFormValues } from '../field-form-schema'
import { scalarDraft, type ScalarDraft, type ScalarDraftControl } from '../scalar-draft'
import { ScalarValueEditor } from './ScalarValueEditor'

type Definition = components['schemas']['DataFieldWrite']
type RuleChoice = 'none' | 'url' | 'length' | 'range' | 'custom'
const urlPattern = '^https?://[^\\s]+$'
const ruleKeys = ['minLength', 'maxLength', 'pattern', 'minimum', 'maximum'] as const

export type FieldEditorFieldsProps = {
  form: UseFormReturn<FieldFormValues>
  defaultDraft?: ScalarDraft
  onDefaultDraftChange?(draft: ScalarDraft): void
  defaultError?: { message: string; control: ScalarDraftControl }
  showDefault?: boolean
  disabled?: boolean
  readOnly?: boolean
  protectedField?: boolean
  keyLocked?: boolean
  typeLocked?: boolean
  presentation?: 'dialog' | 'drawer'
}

export function FieldEditorFields({ form, defaultDraft, onDefaultDraftChange, defaultError, showDefault = false, disabled = false, readOnly = false, protectedField = false, keyLocked = false, typeLocked = false, presentation = 'dialog' }: FieldEditorFieldsProps) {
  const values = useWatch({ control: form.control })
  const [ruleChoice, setRuleChoice] = useState<RuleChoice | null>(null)
  const type = (values.type ?? 'string') as Definition['type']
  const frozen = disabled || readOnly || protectedField
  const drawer = presentation === 'drawer'
  const nameLabel = drawer ? '显示名称' : '字段名称'
  const typeLabel = drawer ? '类型' : '字段类型'
  // Only an explicit preset selection is labelled URL; saved custom patterns remain custom.
  const inferredRule: RuleChoice = values.pattern ? 'custom' : type === 'string' && (values.minLength || values.maxLength) ? 'length' : type === 'number' && (values.minimum || values.maximum) ? 'range' : 'none'
  const chosenRule = ruleChoice === 'url' && (values.pattern !== urlPattern || values.minLength || values.maxLength) ? inferredRule : ruleChoice ?? inferredRule
  const savedRules = JSON.stringify(ruleKeys.map(key => form.formState.defaultValues?.[key]))
  useEffect(() => { setRuleChoice(null) }, [savedRules])

  const changeType = (value: string | null) => {
    if (!value || frozen || typeLocked || value === type) return
    form.setValue('type', value as Definition['type'], { shouldDirty: true })
    onDefaultDraftChange?.(scalarDraft(undefined))
    if (drawer) {
      for (const key of ruleKeys) form.setValue(key, '', { shouldDirty: true })
      form.clearErrors([...ruleKeys])
      setRuleChoice(null)
    }
  }
  const chooseRule = (value: string | null) => {
    if (!value || frozen) return
    const choice = value as RuleChoice
    setRuleChoice(choice)
    if (choice === 'custom') return
    for (const key of ruleKeys) {
      const keep = choice === 'length' && (key === 'minLength' || key === 'maxLength') || choice === 'range' && (key === 'minimum' || key === 'maximum')
      if (!keep) form.setValue(key, choice === 'url' && key === 'pattern' ? urlPattern : '', { shouldDirty: true })
    }
    form.clearErrors([...ruleKeys])
  }
  const ruleOptions = [{ value: 'none', label: '无额外规则' }, ...(type === 'string' ? [{ value: 'url', label: '网址格式' }, { value: 'length', label: '长度限制' }, { value: 'custom', label: '自定义规则' }] : type === 'number' ? [{ value: 'range', label: '数值范围' }] : [])]
  const example = type === 'string' ? chosenRule === 'url' ? 'https://example.com/notes/R013' : '示例文本' : type === 'number' ? '123' : type === 'boolean' ? '是' : '2026-09-14'

  return <>
    <FormField label={nameLabel} htmlFor="field-name" error={form.formState.errors.name?.message}><Input id="field-name" readOnly={frozen} {...form.register('name')} /></FormField>
    <div className="relative grid gap-2"><FormField label="字段键" htmlFor="field-key" error={form.formState.errors.key?.message}><Input id="field-key" className={keyLocked && drawer ? 'pr-10' : undefined} readOnly={frozen || keyLocked} {...form.register('key')} /></FormField>{keyLocked && drawer ? <Lock aria-hidden="true" size={18} className="pointer-events-none absolute right-3 top-[3.25rem] -translate-y-1/2 text-muted" /> : null}{keyLocked ? <p className="m-0 text-sm text-muted">现有字段键保持不变。</p> : null}</div>
    <FormField label={typeLabel} htmlFor="field-type" error={form.formState.errors.type?.message}><Select id="field-type" value={type} options={[{ value: 'string', label: '文本' }, { value: 'number', label: '数字' }, { value: 'boolean', label: '布尔' }, { value: 'date', label: '日期' }]} clearable={false} disabled={disabled} readOnly={readOnly || protectedField || typeLocked} onValueChange={changeType} /></FormField>
    {drawer ? <div className="grid gap-3"><span className="text-base font-medium">必填</span><label className="flex items-center gap-3"><Switch aria-label="必填" checked={Boolean(values.required)} disabled={frozen} onCheckedChange={checked => form.setValue('required', checked, { shouldDirty: true })} /><span>必填</span></label></div> : <label className="flex items-center gap-2"><Checkbox checked={Boolean(values.required)} disabled={frozen} onCheckedChange={checked => form.setValue('required', checked === true, { shouldDirty: true })} />必填</label>}
    <section aria-label="字段校验规则" className="grid gap-3">
      {drawer ? <FormField label="校验规则" htmlFor="field-rule"><Select value={chosenRule} options={ruleOptions} clearable={false} disabled={disabled} readOnly={readOnly || protectedField} onValueChange={chooseRule} /></FormField> : null}
      {type === 'string' && (!drawer || chosenRule === 'length' || chosenRule === 'custom') ? <><FormField label="最小长度" htmlFor="field-min-length" error={form.formState.errors.minLength?.message}><Input id="field-min-length" readOnly={frozen} {...form.register('minLength')} /></FormField><FormField label="最大长度" htmlFor="field-max-length" error={form.formState.errors.maxLength?.message}><Input id="field-max-length" readOnly={frozen} {...form.register('maxLength')} /></FormField></> : null}
      {type === 'string' && (!drawer || chosenRule === 'custom') ? <FormField label="Python 正则表达式" htmlFor="field-pattern" error={form.formState.errors.pattern?.message}><Input id="field-pattern" readOnly={frozen} {...form.register('pattern')} /></FormField> : null}
      {type === 'number' && (!drawer || chosenRule === 'range') ? <><FormField label="最小值" htmlFor="field-minimum" error={form.formState.errors.minimum?.message}><Input id="field-minimum" readOnly={frozen} {...form.register('minimum')} /></FormField><FormField label="最大值" htmlFor="field-maximum" error={form.formState.errors.maximum?.message}><Input id="field-maximum" readOnly={frozen} {...form.register('maximum')} /></FormField></> : null}
    </section>
    {drawer ? <>
      <FormField label="示例值预览" htmlFor="field-example" hint="仅演示填写规则，不会修改记录。"><Input value={example} readOnly /></FormField>
      {chosenRule === 'custom' ? <p className="m-0 text-sm text-muted">自定义规则由服务端预检，示例不代表校验已通过。</p> : null}
      <p className="m-0 flex items-start gap-2 rounded-control border border-warning/20 bg-warning-soft p-4 text-sm text-clay"><Info size={20} className="shrink-0" aria-hidden="true" />更改字段类型会清除原有校验规则，需重新选择。</p>
    </> : null}
    {showDefault && defaultDraft && onDefaultDraftChange ? <><ScalarValueEditor id="field-default" label="现有记录默认值" type={type} draft={defaultDraft} onChange={onDefaultDraftChange} allowMissing disabled={disabled} readOnly={readOnly || protectedField} error={defaultError?.message} errorTarget={defaultError?.control} /><p className="text-xs text-muted">非空表创建必填字段时需要默认值，最终由服务端校验。</p></> : null}
  </>
}
