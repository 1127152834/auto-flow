import { useRef, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { ArrowLeft, Desktop, CheckCircle, Info } from '@phosphor-icons/react'
import { ApiClientError } from '../../../shared/api/client'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Switch } from '../../../shared/components/ui/switch'
import type { AndroidApi, AndroidCreate, AndroidDevice, AndroidEnvironment } from '../api'

type Values = { name: string; imageId: string; width: number; height: number; dpi: number; cpu: number; memoryMb: number; start: boolean }
export function CreateDeviceForm({ environment, source, api, onCreated, onCancel, disabled }: { environment: AndroidEnvironment; source?: AndroidDevice; api: AndroidApi; onCreated(device: AndroidDevice): void; onCancel(): void; disabled: boolean }) {
  const form = useForm<Values>({ defaultValues: { name: source ? `${source.name} 副本` : '测试设备', imageId: source?.imageId ?? environment.images?.[0]?.id ?? '', width: source?.width ?? 720, height: source?.height ?? 1280, dpi: source?.dpi ?? 320, cpu: source?.cpu ?? 1, memoryMb: source?.memoryMb ?? 1536, start: true } })
  const values = form.watch()
  const pending = useRef<AndroidCreate | null>(null)
  const [uncertain, setUncertain] = useState(false)
  const [error, setError] = useState('')
  const submit = form.handleSubmit(async data => {
    setError('')
    const body = pending.current ?? { ...data, name: data.name.trim(), deviceId: crypto.randomUUID() }
    pending.current = body
    try { const device = await api.create(body); onCreated(device) }
    catch (e) {
      const unknown = !(e instanceof ApiClientError) || e.status >= 500
      setUncertain(unknown)
      if (!unknown) pending.current = null
      setError(unknown ? '创建结果尚未确认。请按原编号重试，系统不会重复创建实例。' : e.message)
    }
  })
  const busy = form.formState.isSubmitting
  const errors = form.formState.errors
  const row = 'grid gap-3 sm:grid-cols-[120px_1fr] sm:items-center'
  return <form onSubmit={submit} aria-label="创建安卓实例" className="space-y-4">
    <Button variant="ghost" className="-ml-3 px-3" type="button" disabled={busy} onClick={onCancel}><ArrowLeft size={16} />返回资源看板</Button>
    <div><h1 className="text-2xl font-semibold">{source ? '复制配置，创建实例' : '创建安卓实例'}</h1><p className="mt-2 text-sm text-muted">{source ? '新实例使用独立空白数据，不复制已安装应用或登录状态。' : '在 Mac 运行环境中创建实例，应用和数据独立保存。'}</p></div>
    <div className="grid items-start gap-5 lg:grid-cols-[2fr_1fr]">
      <fieldset disabled={busy || uncertain || disabled} className="divide-y divide-line rounded-card border border-line bg-surface px-6">
        <section className="space-y-5 py-4"><h2 className="flex items-center gap-3 text-lg font-semibold"><span className="flex h-7 w-7 items-center justify-center rounded-full bg-clay text-sm text-white">1</span>基本信息</h2>
          <div className={row}><label htmlFor="device-name" className="text-sm">实例名称</label><div><Input id="device-name" maxLength={80} {...form.register('name', { required: '请输入名称', validate: value => Boolean(value.trim()) || '请输入名称' })} />{errors.name && <p role="alert" className="mt-1 text-xs text-red-700">{errors.name.message}</p>}</div></div>
          <p className="text-xs text-muted">本次创建 1 台持久实例，创建后可继续添加。</p>
        </section>
        <section className="space-y-5 py-4"><h2 className="flex items-center gap-3 text-lg font-semibold"><span className="flex h-7 w-7 items-center justify-center rounded-full bg-clay text-sm text-white">2</span>运行配置</h2>
          <div className={row}><label htmlFor="device-image" className="text-sm">系统镜像</label><Controller name="imageId" control={form.control} rules={{ required: '请选择镜像' }} render={({ field }) => <Select id="device-image" value={field.value || null} onValueChange={value => field.onChange(value ?? '')} onBlur={field.onBlur} options={(environment.images ?? []).map(image => ({ value: image.id, label: image.name }))} placeholder="选择已缓存镜像" clearable={false} />}/></div>
          <p className="rounded-control bg-surface-subtle p-3 text-xs text-muted">软件渲染 · 架构待核实 · Root 能力尚未在此实例验证</p>
          <div className={row}><label htmlFor="device-resolution" className="text-sm">分辨率</label><Select id="device-resolution" value={`${values.width}x${values.height}`} onValueChange={value => { if (!value) return; const [width, height] = value.split('x').map(Number); form.setValue('width', width, { shouldDirty: true }); form.setValue('height', height, { shouldDirty: true }) }} options={[...new Set(['540x960', '720x1280', '1080x1920', `${source?.width ?? 720}x${source?.height ?? 1280}`])].map(size => ({ value: size, label: size.replace('x', ' × ') }))} clearable={false} /></div>
          <details className="rounded-control bg-surface-subtle p-3"><summary className="cursor-pointer text-sm">更多设置 · CPU、内存与显示密度</summary><div className="mt-4 space-y-4">
          <div className={row}><label htmlFor="device-cpu" className="text-sm">CPU 配额</label><Input id="device-cpu" type="number" min={1} max={environment.cpuCount || 8} {...form.register('cpu', { valueAsNumber: true, min: 1, max: environment.cpuCount || 8 })} /></div>
          <div className={row}><label htmlFor="device-memory" className="text-sm">内存 / MiB</label><Input id="device-memory" type="number" min={768} max={8192} step={256} {...form.register('memoryMb', { valueAsNumber: true, min: 768, max: 8192 })} /></div>
          <div className={row}><label htmlFor="device-dpi" className="text-sm">显示密度 / DPI</label><Input id="device-dpi" type="number" min={120} max={640} {...form.register('dpi', { valueAsNumber: true, min: 120, max: 640 })} /></div>
          </div></details>
          {(errors.cpu || errors.memoryMb || errors.dpi) && <p role="alert" className="text-sm text-red-700">请填写配置范围内的数值。</p>}
        </section>
        <section className="space-y-5 py-4"><h2 className="flex items-center gap-3 text-lg font-semibold"><span className="flex h-7 w-7 items-center justify-center rounded-full bg-clay text-sm text-white">3</span>数据与启动</h2><div className="rounded-control border border-clay bg-clay-soft/40 p-4"><h3 className="text-sm font-medium">持久实例</h3><p className="mt-1 text-xs text-muted">停止和结束工作流都会保留应用与数据。</p></div><div className="flex items-center gap-3"><Switch id="device-start" checked={values.start} onCheckedChange={value => form.setValue('start', value, { shouldDirty: true })} /><label htmlFor="device-start" className="text-sm">创建后启动</label></div></section>
      </fieldset>
      <aside className="rounded-card border border-line bg-surface p-6"><h2 className="border-b border-line pb-4 font-semibold">创建预览</h2><dl className="space-y-5 py-6 text-sm">{[['名称', values.name || '未命名'], ['数量', '1 台'], ['系统', environment.images?.find(image => image.id === values.imageId)?.name ?? '系统版本待核实'], ['分辨率', `${values.width} × ${values.height}`], ['资源', `${values.cpu} CPU · ${values.memoryMb} MiB`], ['数据', '独立持久保存']].map(([label, value]) => <div key={label} className="grid grid-cols-[72px_1fr] gap-3"><dt className="text-muted">{label}</dt><dd className="break-words">{value}</dd></div>)}</dl><div className="space-y-4 border-t border-line pt-5 text-sm"><h3 className="font-medium">运行环境</h3><p className="flex items-center gap-3"><Desktop size={20} />Mac 本机</p><p className="flex items-center gap-3 text-sage-strong"><CheckCircle size={20} />{environment.available ? '运行环境已连接' : '环境尚未就绪'}</p><p className="text-xs text-muted">VM：{environment.cpuCount ?? '—'} CPU · {environment.memoryMb ?? '—'} MiB</p><p className="flex gap-2 text-xs text-muted"><Info size={16} className="shrink-0" />启动前会核对内存预算；容器启动后还需等待 Android 就绪。</p></div></aside>
    </div>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    <footer className="sticky bottom-0 -mx-8 flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface px-8 py-4"><Button type="button" disabled={busy} onClick={onCancel}>取消</Button><div className="flex items-center gap-5"><span className="text-xs text-muted">创建进度会显示在资源看板。</span><Button variant="primary" type="submit" disabled={busy || disabled || !values.imageId}>{busy ? '正在提交…' : uncertain ? '按原编号重试创建' : values.start ? '创建并启动' : '创建实例'}</Button></div></footer>
  </form>
}
