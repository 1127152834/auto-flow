import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { FieldGroup } from '../components/FieldGroup'
import { Checkbox } from '../components/ui/checkbox'
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group'
import { Switch } from '../components/ui/switch'
import { Disclosure } from '../components/ui/disclosure'
import { Button } from '../components/ui/button'

const labelClass = 'flex min-h-8 min-w-0 items-start gap-2 text-sm leading-8 text-ink'
export function ToggleCases() {
  const [location, setLocation] = useState('shanghai')
  const [open, setOpen] = useState(false)
  return <section aria-labelledby="toggles-title" className="grid gap-6 rounded-card border border-line bg-surface p-6">
    <header><h2 id="toggles-title" className="font-semibold">勾选、单选与折叠</h2><p className="mt-1 text-xs text-muted">A05 · T4 / 18px 勾选图形、32px 点击区域；Switch 44×24px 轨道。Tab 聚焦，Space 切换，箭头移动单选项。</p></header>
    <div className="grid items-start gap-6 md:grid-cols-3">
      <FieldGroup legend="复选状态">
        <label className={labelClass}><Checkbox />未勾选样本</label>
        <label className={labelClass}><Checkbox defaultChecked />已勾选样本</label>
        <label className={labelClass}><Checkbox defaultChecked="indeterminate" />半选样本</label>
        <label className={labelClass}><Checkbox disabled aria-describedby="disabled-choice-reason" />禁用未选样本</label>
        <label className={labelClass}><Checkbox disabled defaultChecked aria-describedby="disabled-choice-reason" />禁用已选样本</label>
        <label className={labelClass}><Checkbox disabled checked="indeterminate" aria-describedby="disabled-choice-reason" />禁用半选样本</label>
        <p id="disabled-choice-reason" className="text-xs text-muted">样本任务进行中，暂不可修改。</p>
      </FieldGroup>
      <FieldGroup legend={<span id="location-title">位置样本</span>} hint="选择值由调用方管理；不可用项可阅读但不能选择。">
        <RadioGroup aria-labelledby="location-title" value={location} onValueChange={setLocation}>
          <label className={labelClass}><RadioGroupItem value="shanghai" />上海样本</label>
          <label className={labelClass}><RadioGroupItem value="beijing" disabled aria-describedby="radio-disabled-reason" />北京样本</label>
          <label className={labelClass}><RadioGroupItem value="hangzhou" />杭州样本</label>
          <label className={labelClass}><RadioGroupItem value="long" /><span className="min-w-0 break-words">长标签样本：用于验证中文和 English 名称换行后，单选图标保持对齐并且整行可以点击。</span></label>
        </RadioGroup>
        <p id="radio-disabled-reason" className="text-xs text-muted">北京样本暂不可用，方向键应跳过。</p>
      </FieldGroup>
      <FieldGroup legend="开关状态">
        <label className={labelClass}><Switch />关闭样本</label>
        <label className={labelClass}><Switch defaultChecked />开启样本</label>
        <label className={labelClass}><Switch disabled aria-describedby="switch-disabled-reason" />禁用关闭样本</label>
        <label className={labelClass}><Switch defaultChecked disabled aria-describedby="switch-disabled-reason" />禁用开启样本</label>
        <p id="switch-disabled-reason" className="text-xs text-muted">样本设置被锁定，暂不可切换。</p>
      </FieldGroup>
    </div>
    <div className="grid items-start gap-6 md:grid-cols-2">
      <FieldGroup id="radio-error-sample" legend={<span id="radio-error-title">单选组错误样本</span>} error="请选择一项后继续">
        <RadioGroup aria-labelledby="radio-error-title" aria-invalid aria-describedby="radio-error-sample-error">
          <label className={labelClass}><RadioGroupItem value="a" />错误组候选一</label>
          <label className={labelClass}><RadioGroupItem value="b" />错误组候选二</label>
        </RadioGroup>
      </FieldGroup>
      <div className="grid gap-3">
        <Disclosure summary="填写说明样本"><p>每行填写一个路径。折叠内容保持原生 Tab 顺序，收起后不进入键盘焦点。</p><Button size="sm">说明内操作样本</Button></Disclosure>
        <Disclosure summary="受控折叠样本" open={open} onToggle={event => setOpen(event.currentTarget.open)}><p>展开状态与调用方同步，可由外部重置。</p></Disclosure>
        <Button size="sm" onClick={() => setOpen(false)}>收起受控说明</Button>
      </div>
    </div>
    <ToggleFormCase />
  </section>
}
function ToggleFormCase() {
  const [saved, setSaved] = useState(false)
  const { control, handleSubmit, reset, watch } = useForm({ defaultValues: { accepted: false, enabled: false } })
  const enabled = watch('enabled')
  return <form noValidate className="grid gap-3 border-t border-line pt-4" onSubmit={handleSubmit(() => setSaved(true))}>
    <Controller name="accepted" control={control} rules={{ validate: value => value || '请勾选确认项' }} render={({ field, fieldState }) =>
      <FieldGroup legend="开关表单绑定" id="toggle-bound" error={fieldState.error?.message}>
        <label className={labelClass}><Checkbox ref={field.ref} name={field.name} checked={field.value} onCheckedChange={checked => field.onChange(checked === true)} onBlur={field.onBlur} aria-invalid={fieldState.invalid || undefined} aria-describedby={fieldState.error ? 'toggle-bound-error' : undefined} />确认本地样本</label>
      </FieldGroup>} />
    <Controller name="enabled" control={control} render={({ field }) => <label className={labelClass}><Switch ref={field.ref} name={field.name} checked={field.value} onCheckedChange={field.onChange} onBlur={field.onBlur} />启用样本</label>} />
    <div className="flex flex-wrap gap-2"><Button type="submit" variant="primary">提交开关样本</Button><Button onClick={() => { reset(); setSaved(false) }}>重置开关样本</Button></div>
    <p role="status" className="text-sm text-muted">{saved ? `开关样本已保存：已确认 / ${enabled ? '已启用' : '未启用'}` : '开关样本尚未提交'}</p>
  </form>
}
