import type { MouseEventHandler } from 'react'
import { Controller, useFormContext, useWatch } from 'react-hook-form'
import type { InstalledKernel, ProxyOptionsRead } from '../../../shared/api/types'
import { FormField } from '../../../shared/components/FormField'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'
import { Switch } from '../../../shared/components/ui/switch'
import { kernelKey, parseKernelKey, type ProfileFormValues } from '../form-schema'

export type KernelProxyFieldsProps = {
  installedKernels?: readonly InstalledKernel[]
  proxyOptions?: ProxyOptionsRead
  kernelsLoading?: boolean
  kernelsError?: string | null
  proxyOptionsLoading?: boolean
  proxyOptionsError?: string | null
  onManageKernel: MouseEventHandler<HTMLButtonElement>
}

export function KernelProxyFields({
  installedKernels = [],
  proxyOptions = { proxies: [], pools: [] },
  kernelsLoading = false,
  kernelsError,
  proxyOptionsLoading = false,
  proxyOptionsError,
  onManageKernel,
}: KernelProxyFieldsProps) {
  const { control, setValue, formState: { errors } } = useFormContext<ProfileFormValues>()
  const browserKernel = useWatch({ control, name: 'browserKernel' })
  const proxyMode = useWatch({ control, name: 'proxyMode' })
  const proxyId = useWatch({ control, name: 'proxyId' })
  const proxyPoolId = useWatch({ control, name: 'proxyPoolId' })
  const parsedKernel = parseKernelKey(browserKernel)
  const availableKernel = installedKernels.some((kernel) => kernelKey(kernel) === browserKernel)
  const enabledProxies = proxyOptions.proxies.filter((proxy) => proxy.enabled)
  const availableProxy = enabledProxies.some((proxy) => proxy.id === proxyId)
  const availablePool = proxyOptions.pools.some((pool) => pool.id === proxyPoolId)

  return <section aria-labelledby="profile-kernel-proxy-fields" className="grid gap-5">
    <div>
      <h2 id="profile-kernel-proxy-fields" className="m-0 text-lg font-semibold text-ink">内核与代理</h2>
      <p className="mb-0 mt-1 text-sm text-muted">保存时会再次确认内核已安装，并校验代理资源仍然可用。</p>
    </div>
    {kernelsError ? <p role="alert" className="m-0 rounded-control border border-red-200 bg-red-50 p-3 text-sm text-red-800">{kernelsError}</p> : null}
    <div className="grid gap-4">
      <div className="grid gap-2">
        <label className="text-sm font-medium text-ink" htmlFor="profile-browser-kernel">浏览器内核</label>
        <div className="flex gap-2">
          <Controller control={control} name="browserKernel" render={({ field }) => <Select clearable={false} {...field} id="profile-browser-kernel" aria-label="浏览器内核" aria-invalid={Boolean(errors.browserKernel)} aria-describedby={errors.browserKernel ? 'profile-browser-kernel-error' : 'profile-browser-kernel-hint'} className="min-w-0 flex-1" onValueChange={(value) => {
            field.onChange(value ?? '')
            if (parseKernelKey(value ?? '')?.edition === 'public') setValue('releaseChannel', 'stable', { shouldDirty: true, shouldValidate: true })
          }} options={[{ value: '', label: kernelsLoading ? '正在加载内核…' : installedKernels.length ? '请选择已安装内核' : '暂无已安装内核' }, ...(browserKernel && !availableKernel ? [{ value: browserKernel, label: `${parsedKernel ? `${parsedKernel.edition} · ${parsedKernel.version}` : browserKernel}（已不可用）`, disabled: true }] : []), ...installedKernels.map((kernel) => ({ value: kernelKey(kernel), label: `${kernel.edition === 'licensed' ? '正式版' : '公开版'} · ${kernel.version}` }))]} />} />
          <Button type="button" onClick={onManageKernel}>管理内核</Button>
        </div>
        {errors.browserKernel?.message ? <p id="profile-browser-kernel-error" role="alert" className="text-xs text-clay">{errors.browserKernel.message}</p> : <p id="profile-browser-kernel-hint" className="text-xs text-muted">只列出本机已安装的 CloakBrowser 内核。</p>}
      </div>
    </div>
    {proxyOptionsError ? <p role="alert" className="m-0 rounded-control border border-red-200 bg-red-50 p-3 text-sm text-red-800">{proxyOptionsError}</p> : null}
    <div className="grid gap-4 sm:grid-cols-2">
      <FormField label="代理模式" htmlFor="profile-proxy-mode">
        <Controller control={control} name="proxyMode" render={({ field }) => <Select clearable={false} {...field} id="profile-proxy-mode" className="w-full" onValueChange={(value) => {
          field.onChange(value ?? 'none')
          setValue('proxyId', '', { shouldDirty: true, shouldValidate: true })
          setValue('proxyPoolId', '', { shouldDirty: true, shouldValidate: true })
        }} options={[{ value: 'none', label: '不使用代理' }, { value: 'proxy', label: '固定代理' }, { value: 'pool', label: '代理池' }]} />} />
      </FormField>
      {proxyMode === 'proxy' ? <FormField label="固定代理" htmlFor="profile-proxy-id" error={errors.proxyId?.message}>
        <Controller control={control} name="proxyId" render={({ field }) => <Select clearable={false} {...field} id="profile-proxy-id" disabled={proxyOptionsLoading} aria-invalid={Boolean(errors.proxyId)} aria-describedby={errors.proxyId ? 'profile-proxy-id-error' : undefined} className="w-full" onValueChange={value => field.onChange(value ?? '')} options={[{ value: '', label: proxyOptionsLoading ? '正在加载代理…' : enabledProxies.length ? '请选择代理' : '暂无可用代理' }, ...(proxyId && !availableProxy ? [{ value: proxyId, label: `${proxyId}（已不可用）`, disabled: true }] : []), ...enabledProxies.map((proxy) => ({ value: proxy.id, label: proxy.name }))]} />} />
      </FormField> : proxyMode === 'pool' ? <FormField label="代理池" htmlFor="profile-proxy-pool-id" error={errors.proxyPoolId?.message}>
        <Controller control={control} name="proxyPoolId" render={({ field }) => <Select clearable={false} {...field} id="profile-proxy-pool-id" disabled={proxyOptionsLoading} aria-invalid={Boolean(errors.proxyPoolId)} aria-describedby={errors.proxyPoolId ? 'profile-proxy-pool-id-error' : undefined} className="w-full" onValueChange={value => field.onChange(value ?? '')} options={[{ value: '', label: proxyOptionsLoading ? '正在加载代理池…' : proxyOptions.pools.length ? '请选择代理池' : '暂无可用代理池' }, ...(proxyPoolId && !availablePool ? [{ value: proxyPoolId, label: `${proxyPoolId}（已不可用）`, disabled: true }] : []), ...proxyOptions.pools.map((pool) => ({ value: pool.id, label: pool.name }))]} />} />
      </FormField> : <div />}
    </div>
    <div className="grid gap-3 sm:grid-cols-3">
      <BooleanSwitch name="headless" label="无头模式" hint="不显示浏览器窗口。" />
      <BooleanSwitch name="geoip" label="GeoIP" hint="根据代理位置调整地理信息。" />
      <BooleanSwitch name="humanize" label="人类行为模拟" hint="模拟更自然的页面交互。" />
    </div>
  </section>
}

function BooleanSwitch({ name, label, hint }: { name: 'headless' | 'geoip' | 'humanize'; label: string; hint: string }) {
  const { control } = useFormContext<ProfileFormValues>()
  return <label className="flex items-center justify-between gap-3 rounded-control border border-line bg-surface p-3">
    <span><span className="block text-sm font-medium text-ink">{label}</span><span className="mt-1 block text-xs text-muted">{hint}</span></span>
    <Controller control={control} name={name} render={({ field }) => <Switch aria-label={label} checked={field.value} onCheckedChange={field.onChange} onBlur={field.onBlur} />} />
  </label>
}
