import { AutomationResourceSummary, type AutomationResourceSummaryProps } from './AutomationResourceSummary'
import { RadioGroup } from '../../../shared/components/ui/radio-group'
import { Select } from '../../../shared/components/ui/select'
import type { Automation } from '../types'

type Policy = Automation['environmentPolicy']
type ResourceOption = { id: string; name: string }
type ProxyMode = 'inherit' | 'sourceDefault' | 'none' | 'fixed' | 'pool'

export type EnvironmentPolicyEditorProps = {
  value: Policy
  onChange(value: Policy): void
  disabled?: boolean
  nodeBrowserMode?: boolean
  profiles: (ResourceOption & Partial<AutomationResourceSummaryProps['profiles'][number]>)[]
  projectDefaults?: AutomationResourceSummaryProps['projectDefaults']
  proxies: ResourceOption[]
  pools: ResourceOption[]
  modelProviders?: ResourceOption[]
  inputs?: { inputId: string; alias: string }[]
  environments?: ResourceOption[]
  errors?: Record<string, string | undefined>
}

const options = (resources: ResourceOption[], value?: string | null, unavailable = '已保存的资源引用暂不可用') => [
  ...(value && !resources.some(resource => resource.id === value) ? [{ value, label: unavailable, disabled: true }] : []),
  ...resources.map(resource => ({ value: resource.id, label: resource.name })),
]
const withoutProxy = (value: Policy): Policy => { const next = { ...value }; delete next.proxyOverride; return next }

export function EnvironmentPolicyEditor({ value, onChange, disabled = false, nodeBrowserMode = false, profiles, proxies, pools, projectDefaults, modelProviders = [], inputs = [], environments = [], errors = {} }: EnvironmentPolicyEditorProps) {
  const isNew = value.source === 'newFromProfile'
  const profileSpecified = isNew && Object.hasOwn(value, 'profileId')
  const proxyMode: ProxyMode = value.proxyOverride?.mode ?? 'inherit'
  const inputAlias = value.source === 'inputEnvironment' ? inputs.find(input => input.inputId === value.inputId)?.alias.trim() : undefined
  const changeProxyMode = (mode: ProxyMode) => {
    const base = withoutProxy(value)
    if (mode === 'inherit') onChange(base)
    else if (mode === 'sourceDefault' || mode === 'none') onChange({ ...base, proxyOverride: { mode } } as Policy)
    else if (mode === 'fixed' && proxies[0]) onChange({ ...base, proxyOverride: { mode, proxyId: proxies[0].id } } as Policy)
    else if (mode === 'pool' && pools[0]) onChange({ ...base, proxyOverride: { mode, proxyPoolId: pools[0].id } } as Policy)
  }

  return <section className="grid min-w-0 gap-4" aria-label="资源与环境">
    {nodeBrowserMode ? <p className="m-0 text-sm text-muted">浏览器实例由工作流的打开网页节点创建或恢复。模板、代理和内核请在 Studio 节点中配置；项目默认值仅用于新建实例。</p> : <>
    <div className="grid gap-2 md:grid-cols-[12rem_minmax(0,1fr)] md:items-start">
      <label className="pt-2 text-sm font-medium">浏览器配置 <span className="text-danger">*</span></label>
      <div className="grid min-w-0 gap-2 sm:grid-cols-[13rem_minmax(0,1fr)]">
        <Select aria-label="浏览器配置来源" value={profileSpecified ? 'specified' : 'inherit'} options={[{ value: 'inherit', label: '继承项目默认' }, { value: 'specified', label: '指定浏览器配置' }]} clearable={false} disabled={disabled || !isNew} errorMessage={errors.profileSource} onValueChange={mode => {
          if (mode === 'inherit' && value.source === 'newFromProfile') { const next = { ...value }; delete next.profileId; onChange(next) }
          if (mode === 'specified' && value.source === 'newFromProfile') onChange({ ...value, profileId: null })
        }}/>
        {isNew && profileSpecified ? <Select aria-label="浏览器配置" value={value.profileId ?? null} options={options(profiles, value.profileId, '已保存的浏览器配置引用暂不可用')} clearable={false} disabled={disabled} errorMessage={errors.profileId} onValueChange={profileId => onChange({ ...value, profileId })}/> : <p className="m-0 self-center text-sm text-muted">最终采用项目默认浏览器配置</p>}
      </div>
    </div>

    </>}
    <div className="grid gap-2 md:grid-cols-[12rem_minmax(0,1fr)] md:items-start">
      <span className="pt-2 text-sm font-medium">模型提供方</span>
      <Select aria-label="模型提供方" value={Object.hasOwn(value, 'modelProviderId') ? value.modelProviderId ?? 'none' : 'inherit'} options={[{ value: 'inherit', label: '继承项目默认' }, { value: 'none', label: '不指定模型提供方' }, ...options(modelProviders, value.modelProviderId, '已保存的模型提供方引用暂不可用')]} clearable={false} disabled={disabled} errorMessage={errors.modelProviderId} onValueChange={id => {
        if (!id) return
        const next = { ...value }
        if (id === 'inherit') delete next.modelProviderId
        else next.modelProviderId = id === 'none' ? null : id
        onChange(next)
      }}/>
    </div>

    {!nodeBrowserMode && <>
    <div className="grid gap-2 md:grid-cols-[12rem_minmax(0,1fr)] md:items-start">
      <span className="pt-2 text-sm font-medium">代理设置</span>
      <div className="grid gap-3"><RadioGroup label="代理设置" value={proxyMode} disabled={disabled} onValueChange={mode => changeProxyMode(mode as ProxyMode)} options={[
        {value:'inherit',label:'继承项目默认'}, {value:'sourceDefault',label:'跟随浏览器配置'}, {value:'none',label:'不使用代理'},
        {value:'fixed',label:'固定代理',disabled:!proxies.length}, {value:'pool',label:'代理池',disabled:!pools.length},
      ]} />
      {proxyMode === 'fixed' && value.proxyOverride?.mode === 'fixed' ? <Select className="max-w-xl" aria-label="固定代理" value={value.proxyOverride.proxyId} options={options(proxies, value.proxyOverride.proxyId, '已保存的代理引用暂不可用')} clearable={false} disabled={disabled} errorMessage={errors.proxyId} onValueChange={proxyId => proxyId && onChange({ ...value, proxyOverride: { mode: 'fixed', proxyId } } as Policy)}/> : null}
      {proxyMode === 'pool' && value.proxyOverride?.mode === 'pool' ? <Select className="max-w-xl" aria-label="代理池" value={value.proxyOverride.proxyPoolId} options={options(pools, value.proxyOverride.proxyPoolId, '已保存的代理池引用暂不可用')} clearable={false} disabled={disabled} errorMessage={errors.proxyPoolId} onValueChange={proxyPoolId => proxyPoolId && onChange({ ...value, proxyOverride: { mode: 'pool', proxyPoolId } } as Policy)}/> : null}
      </div>
    </div>



    <div className="grid gap-2 md:grid-cols-[12rem_minmax(0,1fr)] md:items-start">
      <span className="pt-2 text-sm font-medium">环境策略</span>
      <div className="grid gap-2"><RadioGroup label="环境策略" value={value.source} disabled={disabled} onValueChange={source => {
        const shared = { ...(value.proxyOverride ? { proxyOverride: value.proxyOverride } : {}), ...(Object.hasOwn(value, 'modelProviderId') ? { modelProviderId: value.modelProviderId } : {}) }
        if (source === 'newFromProfile') onChange({ source, ...shared })
        if (source === 'fixedEnvironment') onChange({ source, environmentId: value.source === 'fixedEnvironment' ? value.environmentId : environments[0]?.id ?? '', ...shared })
        if (source === 'inputEnvironment') onChange({ source, inputId: value.source === 'inputEnvironment' ? value.inputId : inputs[0]?.inputId ?? '', ...shared })
      }} options={[
        {value:'newFromProfile',label:'每个任务创建临时环境'}, {value:'fixedEnvironment',label:'固定保存环境',disabled:disabled && value.source !== 'fixedEnvironment'}, {value:'inputEnvironment',label:'使用记录关联环境',disabled:disabled && value.source !== 'inputEnvironment'},
      ]}/>
      {value.source === 'fixedEnvironment' ? <Select aria-label="保存环境" value={value.environmentId || null} options={options(environments, value.environmentId, '已保存的环境引用暂不可用')} clearable={false} disabled={disabled} errorMessage={errors.environmentId} onValueChange={environmentId => environmentId && onChange({ ...value, source: 'fixedEnvironment', environmentId })}/> : null}
      {value.source === 'inputEnvironment' ? (inputs.length ? <Select aria-label="关联数据输入" value={value.inputId || null} options={inputs.map(input => ({ value: input.inputId, label: input.alias.trim() || '未命名输入' }))} clearable={false} disabled={disabled} errorMessage={errors.inputId} onValueChange={inputId => inputId && onChange({ ...value, source: 'inputEnvironment', inputId })}/> : <p className="m-0 text-sm text-warning">{inputAlias || '已保存的数据输入引用暂不可用'}</p>) : null}
      <p className="m-0 text-sm text-muted">{value.source === 'newFromProfile' ? '任务结束后关闭并清理临时环境，除非明确保留。' : '任务固定当前保存环境的内容代次，执行中不会切换。'}</p>
      </div>
    </div>
    {projectDefaults ? <AutomationResourceSummary policy={value} projectDefaults={projectDefaults} profiles={profiles.flatMap(profile => profile.browserVersion && profile.browserEdition && profile.proxyMode ? [{ ...profile, browserVersion: profile.browserVersion, browserEdition: profile.browserEdition, proxyMode: profile.proxyMode }] : [])} proxies={proxies} pools={pools} models={modelProviders}/> : null}
    </>}
  </section>
}
