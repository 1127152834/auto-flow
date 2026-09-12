import { ArrowClockwise } from '@phosphor-icons/react'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { FormField } from '../components/FormField'
import { FieldGroup } from '../components/FieldGroup'
import { Button } from '../components/ui/button'
import { IconButton } from '../components/ui/icon-button'
import { Input } from '../components/ui/input'
import { Textarea } from '../components/ui/textarea'
import { SearchInput } from '../components/ui/search-input'
import { PasswordInput } from '../components/ui/password-input'

type Size = 'sm' | 'md'
const states = [
  { name: '常规', props: { placeholder: '中文 / English' } },
  { name: '错误', props: { defaultValue: '待修正', 'aria-invalid': true } },
  { name: '只读', props: { defaultValue: '可选择和复制', readOnly: true } },
  { name: '禁用', props: { defaultValue: '暂不可编辑', disabled: true } },
]

export function TextControlCases({ size }: { size: Size }) {
  const [busy, setBusy] = useState(false)
  const [search, setSearch] = useState('日常浏览')
  return <section aria-labelledby="text-controls-title" className="grid gap-6 rounded-card border border-line bg-surface p-6">
    <header><h2 id="text-controls-title" className="font-semibold">按钮与文字控件</h2><p className="mt-1 text-xs text-muted">A03 · T3 / Button、Input、Textarea、SearchInput、PasswordInput、FormField、FieldGroup。密度跟随上方 32/40 切换。</p></header>
    <div aria-label="按钮状态" className="flex flex-wrap items-center gap-3">
      <Button size={size} variant="primary" loading={busy} loadingText="正在保存…" onClick={() => setBusy(true)}>保存样本</Button>
      <Button size={size} onClick={() => setBusy(!busy)}>{busy ? '结束加载样本' : '切换加载样本'}</Button>
      <Button size={size} variant="ghost">次要操作</Button><Button size={size} variant="danger">危险操作样本</Button>
      <Button size={size} disabled>不可用操作</Button>
      <IconButton size={size} aria-label="刷新样本" loading={busy}><ArrowClockwise size={18} /></IconButton>
    </div>
    <p className="text-xs text-muted">Tab 聚焦、Enter / Space 激活；加载保留名称和占位。将系统或设置切为减少动效，加载图标应静止。</p>
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {states.map(({ name, props }) => <FormField key={name} htmlFor={`text-${name}`} label={`${name}文字`} error={name === '错误' ? '请修正样本内容' : undefined} hint={name === '常规' ? '输入法、粘贴和文本选择保持浏览器原生行为。' : undefined}>
        {a11y => <Input {...props} {...a11y} size={size} />}
      </FormField>)}
      {states.map(({ name, props }) => <FormField key={name} htmlFor={`area-${name}`} label={`${name}多行`} error={name === '错误' ? '每行填写一个有效路径' : undefined}>
        {a11y => <Textarea {...props} {...a11y} size={size} defaultValue={name === '只读' ? '第一行：可复制\n第二行：' + '长文本样本 '.repeat(30) : props.defaultValue} />}
      </FormField>)}
      <FormField htmlFor="search-sample" label="搜索样本" hint="清除后焦点回到输入框；查询值仍归调用方。">
        {a11y => <SearchInput {...a11y} size={size} value={search} onChange={e => setSearch(e.target.value)} onClear={() => setSearch('')} />}
      </FormField>
      <FormField htmlFor="search-pending" label="查询中样本">{a11y => <SearchInput {...a11y} size={size} value="保留旧条件" onChange={() => {}} loading />}</FormField>
      <FormField htmlFor="search-error" label="错误搜索" error="目录暂不可用">{a11y => <SearchInput {...a11y} size={size} value="旧条件仍可见" readOnly />}</FormField>
      <FormField htmlFor="search-disabled" label="禁用搜索样本">{a11y => <SearchInput {...a11y} size={size} value="暂不可搜索" disabled />}</FormField>
      <FormField htmlFor="password-sample" label="可显隐密码" hint="仅在业务允许时启用显隐；此处为虚构文本。">
        {a11y => <PasswordInput {...a11y} size={size} allowReveal defaultValue="sample-only-key" />}
      </FormField>
      <FormField htmlFor="password-error" label="错误密码" error="请检查凭据">{a11y => <PasswordInput {...a11y} size={size} defaultValue="sample-only" />}</FormField>
      <FormField htmlFor="password-readonly" label="只读密码">{a11y => <PasswordInput {...a11y} size={size} readOnly defaultValue="sample-only" />}</FormField>
      <FormField htmlFor="password-disabled" label="禁用密码">{a11y => <PasswordInput {...a11y} size={size} disabled defaultValue="sample-only" />}</FormField>
      {states.map(({ name }) => <FormField key={name} htmlFor={`number-${name}`} label={`${name}数字`} error={name === '错误' ? '视口宽度至少为 320' : undefined}>
        {a11y => <Input {...a11y} size={size} type="number" inputMode="numeric" defaultValue={name === '错误' ? '120' : '1280'} min={320} readOnly={name === '只读'} disabled={name === '禁用'} />}
      </FormField>)}
    </div>
    <TextFormCase size={size} />
  </section>
}

function TextFormCase({ size }: { size: Size }) {
  const [saved, setSaved] = useState('')
  const { control, register, handleSubmit, setFocus, reset, formState: { isDirty } } = useForm({ defaultValues: { name: '', description: '', secret: '' } })
  return <form noValidate className="grid gap-4 border-t border-line pt-5" onSubmit={handleSubmit(values => setSaved(values.name))}>
    <FieldGroup legend="真实表单绑定样本" hint="仅使用本地草稿，不写入业务数据。">
      <Controller name="name" control={control} rules={{ required: '请填写样本名称' }} render={({ field, fieldState }) =>
        <FormField htmlFor="bound-name" label="绑定名称" hint="用于识别这份样本。" error={fieldState.error?.message}>
          {a11y => <Input {...field} {...a11y} size={size} placeholder="验证错误聚焦与中文输入" />}
        </FormField>} />
      <FormField htmlFor="bound-description" label="绑定描述">{a11y => <Textarea {...register('description')} {...a11y} size={size} />}</FormField>
      <FormField htmlFor="bound-secret" label="绑定密钥">{a11y => <PasswordInput {...register('secret')} {...a11y} size={size} />}</FormField>
    </FieldGroup>
    <div className="flex flex-wrap gap-2"><Button size={size} type="submit" variant="primary">提交文字样本</Button><Button size={size} onClick={() => setFocus('name')}>聚焦绑定名称</Button><Button size={size} onClick={() => { reset(); setSaved('') }}>重置文字样本</Button></div>
    <p role="status" className="text-sm text-muted">{saved ? `文字样本已保存：${saved}` : isDirty ? '文字草稿有修改' : '文字草稿未修改'}</p>
  </form>
}
