import type { components } from '../../../shared/api/generated'
import { Select } from '../../../shared/components/ui/select'

type Schema = components['schemas']
export type ProxyPolicy = Schema['ProjectDefaultResources']['proxy']
export function validProxy(value: ProxyPolicy, options: Schema['ProxyOptionsRead'] | undefined) {
  return value.mode === 'fixed' ? Boolean(options?.proxies.some(item => item.id === value.proxyId && item.enabled))
    : value.mode === 'pool' ? Boolean(options?.pools.some(item => item.id === value.proxyPoolId)) : true
}

export function ProxyPolicyFields({ value, onChange, options, disabled, sourceDefault = false }: {
  value: ProxyPolicy; onChange(value: ProxyPolicy): void; options?: Schema['ProxyOptionsRead']; disabled?: boolean; sourceDefault?: boolean
}) {
  return <div className="grid gap-3">
    <label className="grid gap-1 text-sm"><span>代理策略</span><Select aria-label="代理策略" value={value.mode} disabled={disabled} clearable={false}
      options={[...(sourceDefault ? [{ value: 'sourceDefault', label: '沿用模板代理' }] : []), { value: 'none', label: '不使用代理' }, { value: 'fixed', label: '固定代理' }, { value: 'pool', label: '代理池' }]}
      onValueChange={mode => { if (mode === 'fixed') onChange({ mode, proxyId: '' }); else if (mode === 'pool') onChange({ mode, proxyPoolId: '' }); else if (mode === 'none' || mode === 'sourceDefault') onChange({ mode }) }} /></label>
    {value.mode === 'fixed' ? <label className="grid gap-1 text-sm"><span>代理</span><Select aria-label="代理" value={value.proxyId || null} disabled={disabled} clearable={false} options={(options?.proxies ?? []).filter(item => item.enabled).map(item => ({ value: item.id, label: item.name }))} onValueChange={id => onChange({ mode: 'fixed', proxyId: id ?? '' })} /></label> : null}
    {value.mode === 'pool' ? <label className="grid gap-1 text-sm"><span>代理池</span><Select aria-label="代理池" value={value.proxyPoolId || null} disabled={disabled} clearable={false} options={(options?.pools ?? []).map(item => ({ value: item.id, label: item.name }))} onValueChange={id => onChange({ mode: 'pool', proxyPoolId: id ?? '' })} /></label> : null}
    {!validProxy(value, options) ? <p role="alert" className="m-0 text-sm text-warning">请选择可用代理。</p> : null}
  </div>
}
