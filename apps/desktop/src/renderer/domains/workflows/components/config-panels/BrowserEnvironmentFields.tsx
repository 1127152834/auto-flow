import {useEffect,useState} from 'react'
import type {components} from '../../../../shared/api/generated'
import type {BrowserEnvironment} from '../../types/workflow'
import type {NodeData} from '../../editor-store'
import {useWorkflowStore} from '../../editor-store'
import {apiRequest,browserApi} from '../../api'
import {getStudioOpenContext} from '../../api/config'
import {getStudioTransportRevision} from '../../api/transport'
import {useGlobalConfigStore} from '../../hooks/stores/globalConfigStore'
import {Label} from '../controls/label'
import {SelectNative as Select} from '../controls/select-native'
import {Input} from '../controls/input'
import {Button} from '../controls/button'

type Schema=components['schemas']
export function BrowserEnvironmentFields({data,onChange}:{data:NodeData;onChange(key:string,value:unknown):void}) {
 const version=useWorkflowStore(state=>state.browserEnvironmentVersion)
 const nodeId=useWorkflowStore(state=>state.selectedNodeId)
 const projectId=getStudioOpenContext().projectId
 const [legacy,setLegacy]=useState<BrowserEnvironment>({source:'newFromProfile',profileId:useGlobalConfigStore.getState().config.browserProfileId||null})
 const value=(version===1?data.browserEnvironment:legacy) as BrowserEnvironment|undefined
 const change=(next:BrowserEnvironment)=>version===1?onChange('browserEnvironment',next):setLegacy(next)
 const [profiles,setProfiles]=useState<Schema['ProfileRead'][]>([])
 const [kernels,setKernels]=useState<Schema['InstalledKernelList']['items']>([])
 const [proxies,setProxies]=useState<Schema['ProxyOptionsRead']>()
 const [environments,setEnvironments]=useState<Schema['EnvironmentView'][]>([])
 const [error,setError]=useState(''),[refresh,setRefresh]=useState(0)
 useEffect(()=>{
  const controller=new AbortController(),revision=getStudioTransportRevision()
  setError('')
  void Promise.all([browserApi.profiles(),apiRequest<Schema['InstalledKernelList']>('/v1/kernels/installed',{signal:controller.signal}),apiRequest<Schema['ProxyOptionsRead']>('/v1/proxy-options',{signal:controller.signal})]).then(([p,k,x])=>{
   if(controller.signal.aborted||revision!==getStudioTransportRevision())return
   setProfiles(p.data?.items??[]);setKernels(k.data?.items??[]);setProxies(x.data)
   if(!p.success||!k.success||!x.success)setError(p.error||k.error||x.error||'资源目录读取失败')
  })
  if(projectId)void (async()=>{
   const items:Schema['EnvironmentView'][]=[]
   for(let page=1;;page++){
    const result=await apiRequest<Schema['EnvironmentPage']>(`/v1/projects/${encodeURIComponent(projectId)}/environments?page=${page}&pageSize=100&sort=name&state=ready`,{signal:controller.signal})
    if(controller.signal.aborted||revision!==getStudioTransportRevision())return
    if(!result.success||!result.data){setError(result.error||'环境目录读取失败');return}
    items.push(...result.data.items)
    if(items.length>=result.data.total||!result.data.items.length)break
   }
   setEnvironments(items)
  })()
  return()=>controller.abort()
 },[projectId,refresh])
 useEffect(()=>{const reload=()=>setRefresh(n=>n+1);window.addEventListener('studio:transport-changed',reload);window.addEventListener('studio:connection-restored',reload);return()=>{window.removeEventListener('studio:transport-changed',reload);window.removeEventListener('studio:connection-restored',reload)}},[])
 const proxy=value?.source==='newFromProfile'?value.proxy??{mode:'projectDefault'}:null
 return <section className="space-y-3" aria-label="浏览器环境">
  {version!==1&&<p className="text-xs text-muted-foreground">旧工作流尚未迁移。选择此节点的新建设置后，点击下方迁移按钮；其他打开网页节点将使用当前实例。</p>}
  <div className="space-y-2"><Label htmlFor="browser-environment-source">环境来源</Label><Select id="browser-environment-source" value={value?.source??''} onChange={event=>{const source=event.target.value;if(source==='current')change({source});if(source==='newFromProfile')change({source});if(source==='fixedEnvironment')change({source,environmentId:''});if(source==='inputEnvironment')change({source,inputId:''})}}>
   <option value="" disabled>请选择环境来源</option><option value="newFromProfile">基于模板新建实例</option><option value="current">使用当前实例</option><option value="fixedEnvironment" disabled={!projectId}>使用项目已有环境</option><option value="inputEnvironment" disabled={!projectId}>使用任务输入关联环境</option>
  </Select></div>
  {value?.source==='newFromProfile'&&<>
   <div className="space-y-2"><Label htmlFor="node-browser-template">浏览器模板</Label><Select id="node-browser-template" value={value.profileId??''} onChange={event=>change({...value,profileId:event.target.value||null})}>
    <option value="">{projectId?'使用项目默认模板':'请选择浏览器模板'}</option>{value.profileId&&!profiles.some(p=>p.id===value.profileId)&&<option value={value.profileId}>所选模板不可用</option>}{profiles.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
   </Select></div>
   <div className="space-y-2"><Label htmlFor="node-browser-proxy">代理</Label><Select id="node-browser-proxy" value={proxy?.mode} onChange={event=>{const mode=event.target.value;if(mode==='fixed')change({...value,proxy:{mode,proxyId:''}});else if(mode==='pool')change({...value,proxy:{mode,proxyPoolId:''}});else if(mode==='projectDefault'||mode==='sourceDefault'||mode==='none')change({...value,proxy:{mode}})}}>
    <option value="projectDefault">使用项目默认代理</option><option value="sourceDefault">使用模板代理</option><option value="none">不使用代理</option><option value="fixed">指定代理</option><option value="pool">使用代理池</option>
   </Select></div>
   {proxy?.mode==='fixed'&&<Select aria-label="指定代理" value={proxy.proxyId??''} onChange={event=>change({...value,proxy:{mode:'fixed',proxyId:event.target.value}})}><option value="">请选择代理</option>{proxies?.proxies.filter(p=>p.enabled).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</Select>}
   {proxy?.mode==='pool'&&<Select aria-label="代理池" value={proxy.proxyPoolId??''} onChange={event=>change({...value,proxy:{mode:'pool',proxyPoolId:event.target.value}})}><option value="">请选择代理池</option>{proxies?.pools.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</Select>}
   <div className="space-y-2"><Label htmlFor="node-browser-kernel">浏览器内核</Label><Select id="node-browser-kernel" value={value.kernel?`${value.kernel.edition}:${value.kernel.version}`:''} onChange={event=>{const kernel=kernels.find(k=>`${k.edition}:${k.version}`===event.target.value);change({...value,kernel:kernel?{edition:kernel.edition,version:kernel.version}:null})}}>
    <option value="">使用模板内核</option>{value.kernel&&!kernels.some(k=>k.edition===value.kernel?.edition&&k.version===value.kernel?.version)&&<option value={`${value.kernel.edition}:${value.kernel.version}`}>所选内核未安装</option>}{kernels.map(k=><option key={`${k.edition}:${k.version}`} value={`${k.edition}:${k.version}`}>{k.edition==='public'?'公开版':'授权版'} {k.version}</option>)}
   </Select><p className="text-xs text-muted-foreground">在浏览器配置中安装所需内核。设置仅作用于新实例。</p></div>
  </>}
  {value?.source==='fixedEnvironment'&&<><Label htmlFor="node-saved-environment">保存环境</Label><Select id="node-saved-environment" value={value.environmentId} onChange={event=>change({...value,environmentId:event.target.value})}><option value="">请选择环境</option>{environments.map(e=><option key={e.ref.environmentId} value={e.ref.environmentId}>{e.name}</option>)}</Select><p className="text-xs text-muted-foreground">使用环境自身的代理和内核；调试副本不会自动覆盖原环境。</p></>}
  {value?.source==='inputEnvironment'&&<><Label htmlFor="node-environment-input">已声明输入 ID</Label><Input id="node-environment-input" value={value.inputId} onChange={event=>change({...value,inputId:event.target.value})}/><p className="text-xs text-muted-foreground">从项目自动化领取的输入记录恢复环境；独立 Studio 调试请选择固定环境。</p></>}
  {value?.source==='current'&&<p className="text-xs text-muted-foreground">继续使用本次运行已创建的实例；请先执行初始化节点。</p>}
  {version!==1&&<Button disabled={!nodeId||!value||value.source==='current'} onClick={()=>{if(nodeId&&value)useWorkflowStore.getState().migrateBrowserEnvironment(nodeId,value)}}>将此节点设为初始化入口并迁移</Button>}
  {error&&<p role="alert" className="text-xs text-destructive">{error}</p>}
  <Button variant="ghost" size="sm" onClick={()=>setRefresh(n=>n+1)}>刷新浏览器资源</Button>
 </section>
}
