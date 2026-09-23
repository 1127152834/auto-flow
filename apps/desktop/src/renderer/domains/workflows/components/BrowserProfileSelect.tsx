import {useEffect,useState} from 'react'
import type {components} from '../../../shared/api/generated'
import {browserApi, projectResourceApi} from '../api'
import {getStudioResourceScope} from '../api/config'
import {getStudioTransportRevision} from '../api/transport'
import {useGlobalConfigStore} from '../hooks/stores/globalConfigStore'

/** AutoFlow host adaptation: choose managed Profiles; never edit launch parameters here. */
export function BrowserProfileSelect({label='浏览器配置',disabled=false,value,onChange}:{label?:string;disabled?:boolean;value?:string;onChange?:(profileId:string)=>void}) {
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
  return <label className="flex flex-wrap items-center gap-1 text-xs" title="仅使用管理端 CloakBrowser 配置；启动参数在管理端维护">
    {label}
    <select aria-label={label} disabled={disabled||loading} value={profileId||''} onChange={event=>select(event.target.value)} className="max-w-48 rounded border bg-[hsl(var(--card))] px-2 py-1">
      <option value="">{loading?'正在读取配置…':profiles.length?'请选择配置':'暂无配置，请在管理端创建'}</option>
      {profileId&&!profiles.some(profile=>profile.id===profileId)&&<option value={profileId}>所选配置已不可用，请重新选择</option>}
      {profiles.map(profile=><option key={profile.id} value={profile.id}>{profile.name}</option>)}
    </select>
    <button type="button" disabled={disabled||loading} onClick={()=>setAttempt(value=>value+1)}>刷新配置</button>
    {error&&<span role="alert">{error}</span>}
  </label>
}
