import {useEffect,useId,useState} from 'react'
import { Globe, RefreshCw } from 'lucide-react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './controls/select'
import { Button } from './controls/button'
import type {components} from '../../../shared/api/generated'
import {browserApi, projectResourceApi} from '../api'
import {getStudioResourceScope} from '../api/config'
import {getStudioTransportRevision} from '../api/transport'
import {useGlobalConfigStore} from '../hooks/stores/globalConfigStore'

/** AutoFlow host adaptation: choose managed Profiles; never edit launch parameters here. */
export function BrowserProfileSelect({label='浏览器配置',disabled=false,value,onChange}:{label?:string;disabled?:boolean;value?:string;onChange?:(profileId:string)=>void}) {
  const controlId=useId()
  const globalProfileId=useGlobalConfigStore(state=>state.config.browserProfileId)
  const selectGlobal=useGlobalConfigStore(state=>state.setBrowserProfileId)
  const resources=useGlobalConfigStore(state=>state.projectResources)
  const scope=getStudioResourceScope()
  const profileId=value??(scope ? resources.scope===scope ? resources.profileId??resources.defaults?.profileId??'' : '' : globalProfileId)
  const select=onChange??selectGlobal
  const [profiles,setProfiles]=useState<components['schemas']['ProfileRead'][]>([])
  const [loading,setLoading]=useState(true),[error,setError]=useState(''),[attempt,setAttempt]=useState(0)
  useEffect(()=>{
    let active=true
    const connection=getStudioTransportRevision()
    setLoading(true);setError('')
    void Promise.all([browserApi.profiles(), projectResourceApi.defaults()]).then(([result, defaults])=>{
      if(!active||connection!==getStudioTransportRevision()||scope!==getStudioResourceScope())return
      setLoading(false)
      if(!defaults.success){setProfiles([]);setError(defaults.error||'项目默认资源读取失败');return}
      if(!result.success||!result.data){setProfiles([]);setError(result.error||'浏览器配置读取失败');return}
      setProfiles(result.data.items)
      // Read the latest selection: a refresh must not overwrite an explicit choice.
      if(onChange){
        if(!value){const initial=scope?defaults.data?.profileId:result.data.items[0]?.id;if(initial)onChange(initial)}
      } else if(!scope&&!useGlobalConfigStore.getState().config.browserProfileId&&result.data.items.length)select(result.data.items[0].id)
    })
    return()=>{active=false}
  },[attempt,select,scope,onChange,value])
  useEffect(()=>{
    const reload=()=>{setProfiles([]);setAttempt(value=>value+1)}
    window.addEventListener('studio:transport-changed',reload);window.addEventListener('studio:connection-restored',reload)
    return()=>{window.removeEventListener('studio:transport-changed',reload);window.removeEventListener('studio:connection-restored',reload)}
  },[])
  const options=profiles.map(profile=>({value:profile.id,label:profile.name,disabled:false}))
  if(profileId&&!profiles.some(profile=>profile.id===profileId)) {
    options.unshift({value:profileId,label:'所选配置已不可用，请重新选择',disabled:true})
  }
  return <div className="flex max-w-full flex-wrap items-center gap-2 text-xs">
    <label htmlFor={controlId} className="whitespace-nowrap text-[hsl(var(--muted-foreground))]"
      title="仅使用管理端 CloakBrowser 配置；启动参数在管理端维护">{label}</label>
    <div className="flex min-w-0 max-w-full items-center gap-1">
      <Select value={profileId||''} onValueChange={select} disabled={disabled||loading}>
        <SelectTrigger id={controlId} aria-label={label} data-choice-value={profileId||''}
          aria-invalid={!!error} className="w-52 max-w-full">
          <div className="flex min-w-0 items-center gap-2">
            <Globe className="h-3.5 w-3.5 shrink-0 text-[hsl(var(--brand-600))]" aria-hidden="true"/>
            <span className="truncate"><SelectValue placeholder={loading?'正在读取配置…':profiles.length?'请选择配置':'暂无配置，请在管理端创建'}/></span>
          </div>
        </SelectTrigger>
        <SelectContent sideOffset={4} collisionPadding={12} className="max-w-[min(24rem,calc(100vw-2rem))]">
          {options.map(option=><SelectItem key={option.value} value={option.value} data-choice-value={option.value}
            disabled={option.disabled} className="whitespace-normal break-words">{option.label}</SelectItem>)}
          {!profiles.length&&!profileId&&<p className="px-3 py-2 text-xs text-[hsl(var(--muted-foreground))]">请先在管理端创建浏览器配置</p>}
        </SelectContent>
      </Select>
      <Button type="button" aria-label="刷新配置" title="刷新浏览器配置" size="icon-sm" variant="ghost"
        disabled={disabled||loading} aria-busy={loading} className="h-8 w-8 shrink-0"
        onClick={()=>setAttempt(value=>value+1)}>
        <RefreshCw className={`h-3.5 w-3.5${loading?' animate-spin':''}`} aria-hidden="true"/>
      </Button>
    </div>
    {error&&<span role="alert" className="basis-full text-[hsl(var(--destructive))]">{error}</span>}
  </div>
}
