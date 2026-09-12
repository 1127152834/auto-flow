import { useEffect, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { Button } from '../components/ui/button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs'
import { LabCombobox } from './LabCombobox'
import { kernelOptions } from './fixtures'

export function FormFocusCase() {
  const [saved, setSaved] = useState('')
  const [tab, setTab] = useState('environment')
  const [focusPending, setFocusPending] = useState(false)
  const { control, handleSubmit, reset, setFocus, formState: { isDirty, touchedFields } } = useForm<{ kernel: string | null }>({ defaultValues: { kernel: null }, shouldFocusError: false })
  useEffect(() => { if (focusPending && tab === 'environment') { setFocus('kernel'); setFocusPending(false) } }, [focusPending, tab, setFocus])
  const focusKernel = () => { setTab('environment'); setFocusPending(true) }
  return <form onSubmit={handleSubmit(values => setSaved(values.kernel ?? ''), focusKernel)} className="grid gap-4">
    <Tabs value={tab} onValueChange={setTab}><TabsList aria-label="验证表单页签"><TabsTrigger value="basic">验证基础</TabsTrigger><TabsTrigger value="environment">验证环境</TabsTrigger></TabsList>
      <TabsContent value="basic"><p className="text-sm text-muted">在此页提交空表单，应先切换到错误字段所在页，再聚焦输入框。</p></TabsContent>
      <TabsContent value="environment" forceMount hidden={tab !== 'environment'}><Controller name="kernel" control={control} rules={{ required: '请选择浏览器内核' }} render={({ field, fieldState }) =>
        <LabCombobox label="验证内核" options={kernelOptions} value={field.value} onValueChange={field.onChange} inputRef={field.ref} onBlur={field.onBlur} error={fieldState.error?.message} />} /></TabsContent>
    </Tabs>
    <div className="flex flex-wrap gap-2"><Button onClick={focusKernel}>定位验证内核</Button><Button type="submit" variant="primary">验证保存</Button><Button onClick={() => { reset(); setSaved('') }}>重置表单</Button></div>
    <p role="status" className="text-sm text-muted">{saved ? `已保存验证值：${saved}` : isDirty ? '表单有修改' : '表单未修改'}</p>
    <p className="text-xs text-muted">{touchedFields.kernel ? '字段已访问' : '字段未访问'}</p>
  </form>
}
