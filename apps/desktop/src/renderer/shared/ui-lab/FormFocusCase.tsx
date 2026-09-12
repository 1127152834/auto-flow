import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { Button } from '../components/ui/button'
import { LabCombobox } from './LabCombobox'
import { kernelOptions } from './fixtures'

export function FormFocusCase() {
  const [saved, setSaved] = useState('')
  const { control, handleSubmit, reset, setFocus, formState: { isDirty } } = useForm({ defaultValues: { kernel: '' } })
  return <form onSubmit={handleSubmit(values => setSaved(values.kernel))} className="grid gap-4">
    <Controller name="kernel" control={control} rules={{ required: '请选择浏览器内核' }} render={({ field, fieldState }) =>
      <LabCombobox label="验证内核" options={kernelOptions} value={field.value || null} onValueChange={value => field.onChange(value ?? '')}
        inputRef={field.ref} onBlur={field.onBlur} error={fieldState.error?.message} />} />
    <div className="flex flex-wrap gap-2"><Button type="button" onClick={() => setFocus('kernel')}>定位验证内核</Button><Button type="submit" variant="primary">验证保存</Button><Button type="button" onClick={() => { reset(); setSaved('') }}>重置表单</Button></div>
    <p role="status" className="text-sm text-muted">{saved ? `已保存验证值：${saved}` : isDirty ? '表单有修改' : '表单未修改'}</p>
  </form>
}
