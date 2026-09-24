import {useEffect,useState} from 'react'
import type {components} from '../../../../shared/api/generated'
import type {BrowserEnvironment} from '../../types/workflow'
import type {NodeData} from '../../editor-store'
import {useWorkflowStore} from '../../editor-store'
import {apiRequest,browserApi} from '../../api'
import {getStudioTransportRevision} from '../../api/transport'
import {Label} from '../controls/label'
import {SelectNative as Select} from '../controls/select-native'
import {Button} from '../controls/button'

type Schema=components['schemas']
type ProfileSelection=Extract<BrowserEnvironment,{source:'profile'|'newFromProfile'}>
export function BrowserEnvironmentFields({data,onChange}:{data:NodeData;onChange(key:string,value:unknown):void}) {
 const version=useWorkflowStore(state=>state.browserEnvironmentVersion)
 const nodeId=useWorkflowStore(state=>state.selectedNodeId)
 const [legacy,setLegacy]=useState<ProfileSelection>({source:'profile'})
 const saved=(version===1?data.browserEnvironment:legacy) as BrowserEnvironment|undefined
 const value:ProfileSelection=saved?.source==='profile'||saved?.source==='newFromProfile'?saved:{source:'profile'}
 const change=(next:ProfileSelection)=>version===1?onChange('browserEnvironment',{...next,source:'profile'}):setLegacy({...next,source:'profile'})
 const [profiles,setProfiles]=useState<Schema['ProfileRead'][]>([])
 const [kernels,setKernels]=useState<Schema['InstalledKernelList']['items']>([])
 const [proxies,setProxies]=useState<Schema['ProxyOptionsRead']>()
 const [error,setError]=useState(''),[refresh,setRefresh]=useState(0)
 useEffect(()=>{
  const controller=new AbortController(),revision=getStudioTransportRevision()
  setError('')
  void Promise.all([browserApi.profiles(),apiRequest<Schema['InstalledKernelList']>('/v1/kernels/installed',{signal:controller.signal}),apiRequest<Schema['ProxyOptionsRead']>('/v1/proxy-options',{signal:controller.signal})]).then(([p,k,x])=>{
   if(controller.signal.aborted||revision!==getStudioTransportRevision())return
   setProfiles(p.data?.items??[]);setKernels(k.data?.items??[]);setProxies(x.data)
   if(!p.success||!k.success||!x.success)setError(p.error||k.error||x.error||'资源目录读取失败')
  })
  return()=>controller.abort()
 },[refresh])
 useEffect(()=>{const reload=()=>setRefresh(n=>n+1);window.addEventListener('studio:transport-changed',reload);window.addEventListener('studio:connection-restored',reload);return()=>{window.removeEventListener('studio:transport-changed',reload);window.removeEventListener('studio:connection-restored',reload)}},[])
 const proxy=value.proxy??{mode:value.source==='newFromProfile'?'projectDefault':'sourceDefault'}
 const oldProxy=proxy.mode==='projectDefault'||proxy.mode==='pool'
 return <section className="space-y-3" aria-label="浏览器设置">
  {(version!==1||saved?.source!=='profile')&&<p className="text-xs text-muted-foreground">此节点保留旧版设置。选择浏览器配置后应用新设置；修改前仍按原设置运行。</p>}
  <div className="space-y-2"><Label htmlFor="node-browser-template">浏览器配置</Label><Select id="node-browser-template" aria-required="true" aria-invalid={!value.profileId} value={value.profileId??''} onChange={event=>change({...value,profileId:event.target.value||null,...(oldProxy?{proxy:{mode:'sourceDefault' as const}}:{})})}>
   <option value="" disabled>请选择浏览器配置（必选）</option>{value.profileId&&!profiles.some(p=>p.id===value.profileId)&&<option value={value.profileId}>所选浏览器配置不可用</option>}{profiles.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
  </Select><p className="text-xs text-muted-foreground">相同配置共用浏览器，保留登录状态。</p></div>
  <div className="space-y-2"><Label htmlFor="node-browser-proxy">代理</Label><Select id="node-browser-proxy" value={proxy.mode} onChange={event=>{const mode=event.target.value;if(mode==='fixed')change({...value,proxy:{mode,proxyId:''}});else if(mode==='sourceDefault'||mode==='none')change({...value,proxy:{mode}})}}>
   {oldProxy&&<option value={proxy.mode} disabled>旧版代理设置，请重新选择</option>}
   <option value="sourceDefault">沿用浏览器配置</option><option value="none">不使用代理</option><option value="fixed">指定代理</option>
  </Select></div>
  {proxy.mode==='fixed'&&<Select aria-label="指定代理" value={proxy.proxyId??''} onChange={event=>change({...value,proxy:{mode:'fixed',proxyId:event.target.value}})}><option value="">请选择代理</option>{proxies?.proxies.filter(p=>p.enabled).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</Select>}
  <div className="space-y-2"><Label htmlFor="node-browser-kernel">浏览器内核</Label><Select id="node-browser-kernel" value={value.kernel?`${value.kernel.edition}:${value.kernel.version}`:''} onChange={event=>{const kernel=kernels.find(k=>`${k.edition}:${k.version}`===event.target.value);change({...value,kernel:kernel?{edition:kernel.edition,version:kernel.version}:null})}}>
   <option value="">沿用浏览器配置</option>{value.kernel&&!kernels.some(k=>k.edition===value.kernel?.edition&&k.version===value.kernel?.version)&&<option value={`${value.kernel.edition}:${value.kernel.version}`}>所选内核未安装</option>}{kernels.map(k=><option key={`${k.edition}:${k.version}`} value={`${k.edition}:${k.version}`}>{k.edition==='public'?'公开版':'授权版'} {k.version}</option>)}
  </Select></div>
  {version!==1&&<Button disabled={!nodeId||!value.profileId||oldProxy} onClick={()=>{if(nodeId&&value.profileId)useWorkflowStore.getState().migrateBrowserEnvironment(nodeId,{...value,source:'profile'})}}>将此浏览器配置应用到工作流</Button>}
  {error&&<p role="alert" className="text-xs text-destructive">{error}</p>}
  <Button variant="ghost" size="sm" onClick={()=>setRefresh(n=>n+1)}>刷新浏览器配置</Button>
 </section>
}
