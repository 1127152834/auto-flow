import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {configureStudioConnection} from '../api/config'
import {fetchRequiredFields,getMissingRequired,getMissingRequiredLabels,isRequiredFieldMetadata,useRequiredFields} from '../lib/requiredFields'
import {ConfigPanel} from '../components/ConfigPanel'
import {useWorkflowStore} from '../editor-store'
const metadata={schemaRevision:'test',coveredModules:['open_page','demo'],requiredFields:{open_page:['url']},conditionalRequired:{demo:{field:'mode',default:'first',map:{first:['one'],second:['two'],empty:[]}}},fieldLabels:{open_page:{url:'目标网址'}}}
const pending=<T,>()=>{let resolve!:(value:T)=>void;const promise=new Promise<T>(r=>{resolve=r});return{promise,resolve}}
let restores:Array<()=>void>
let request:ReturnType<typeof vi.fn<(input:RequestInfo|URL,init?:RequestInit)=>Promise<Response>>>
beforeEach(()=>{restores=[];request=vi.fn(async()=>Response.json(metadata));restores.push(configureStudioConnection('http://metadata.invalid',request));useWorkflowStore.getState().clearWorkflow()})
afterEach(()=>{cleanup();restores.reverse().forEach(restore=>restore());vi.restoreAllMocks()})
function Rules(){const result=useRequiredFields();return <div>{result.loading?<span role="status">加载中</span>:result.error?<p role="alert">{result.error}</p>:<span>{result.data!.schemaRevision}</span>}<button onClick={result.retry}>重试</button></div>}
it('shares concurrent requests and caches only successful metadata',async()=>{
 const response=pending<Response>();request.mockReturnValue(response.promise)
 render(<><Rules/><Rules/></>);expect(screen.getAllByRole('status')).toHaveLength(2)
 await waitFor(()=>expect(request).toHaveBeenCalledOnce());await act(async()=>response.resolve(Response.json(metadata)))
 expect(screen.getAllByText('test')).toHaveLength(2);await fetchRequiredFields();expect(request).toHaveBeenCalledOnce()
})
it('shows failure and retries instead of permanently caching empty rules',async()=>{
 request.mockResolvedValueOnce(Response.json({error:'规则服务离线'},{status:503}))
 render(<Rules/>);expect((await screen.findByRole('alert')).textContent).toContain('规则服务离线')
 fireEvent.click(screen.getByRole('button',{name:'重试'}));await screen.findByText('test');expect(request).toHaveBeenCalledTimes(2)
})
it('rejects HTTP200 error payloads and allows a later retry',async()=>{
 request.mockResolvedValueOnce(Response.json({requiredFields:{},conditionalRequired:{},error:'后端读取失败'}))
 await expect(fetchRequiredFields()).rejects.toThrow();expect(await fetchRequiredFields()).toEqual(metadata);expect(request).toHaveBeenCalledTimes(2)
})
it.each(['http://replacement.invalid','http://metadata.invalid'])('does not apply a late response after transport replacement at %s',async origin=>{
 const response=pending<Response>();request.mockReturnValue(response.promise);render(<Rules/>)
 await waitFor(()=>expect(request).toHaveBeenCalledOnce())
 await act(async()=>{restores.push(configureStudioConnection(origin,async()=>Response.json({...metadata,schemaRevision:'replacement'})))})
 await screen.findByText('replacement');await act(async()=>response.resolve(Response.json(metadata)))
 expect(screen.queryByText('test')).toBeNull();expect(screen.getByText('replacement')).toBeTruthy()
})
it('refreshes rules after an ordinary connection-restored event',async()=>{
 render(<Rules/>);await screen.findByText('test');request.mockResolvedValue(Response.json({...metadata,schemaRevision:'restored'}))
 act(()=>window.dispatchEvent(new Event('studio:connection-restored')));await screen.findByText('restored');expect(request).toHaveBeenCalledTimes(2)
})
it('explicit retry refreshes a successful cache',async()=>{
 render(<Rules/>);await screen.findByText('test');request.mockResolvedValue(Response.json({...metadata,schemaRevision:'updated'}))
 fireEvent.click(screen.getByRole('button',{name:'重试'}));await screen.findByText('updated')
})
it.each([['first',['one']],['second',['two']],['empty',[]],['unknown',[]],['constructor',[]],['',['one']],[undefined,['one']]] as const)('evaluates the current conditional branch %s', (mode,expected)=>{
 expect(getMissingRequired('demo',{mode},{},metadata.conditionalRequired)).toEqual(expected)
})
it.each([0,false])('accepts present scalar value %j',value=>expect(getMissingRequired('demo',{one:value},{demo:['one']})).toEqual([]))
it.each([' ',null,undefined,[]])('detects missing value %j',value=>expect(getMissingRequired('demo',{one:value},{demo:['one']})).toEqual(['one']))
it('uses service labels and safely falls back for unknown labels or prototype names',()=>{
 expect(getMissingRequiredLabels('open_page',{},metadata.requiredFields,metadata)).toEqual(['目标网址'])
 expect(getMissingRequiredLabels('demo',{}, {demo:['selector']})).toEqual(['元素选择器'])
 expect(getMissingRequired('constructor',{},{})).toEqual([])
})
it.each([
 {coveredModules:['demo','demo']},{requiredFields:{foreign:['url']}},{requiredFields:{demo:['']}},
 {requiredFields:{demo:['one','one']}},{fieldLabels:{demo:{one:42}}},{schemaRevision:''},
 {conditionalRequired:{demo:{field:'',default:null,map:{}}}},
 {conditionalRequired:{demo:{field:'mode',default:null,map:{a:['x','x']}}}},
 {conditionalRequired:{demo:{field:'mode',map:{}}}},
 {success:true},
])('rejects inconsistent metadata %j',patch=>expect(isRequiredFieldMetadata({...metadata,...patch})).toBe(false))
it('shows rule loading failure, retries, then shows the actual missing URL in ConfigPanel',async()=>{
 let firstRuleRead=true
 request.mockImplementation(async input=>{if(String(input).includes('required-fields')&&firstRuleRead){firstRuleRead=false;return Response.json({error:'字段服务暂不可用'},{status:503})}return Response.json(metadata)})
 useWorkflowStore.getState().addNode('open_page',{x:0,y:0},{url:''});render(<ConfigPanel selectedNodeId={useWorkflowStore.getState().nodes[0].id}/>);fireEvent.click(screen.getByTitle('展开配置面板'))
 await screen.findByRole('button',{name:'重新读取字段规则'});fireEvent.click(screen.getByRole('button',{name:'重新读取字段规则'}))
 await screen.findByText('有 1 个必填项未填写：');expect(screen.getByText('目标网址')).toBeTruthy()
})
it('distinguishes missing coverage from a covered node with no required fields',async()=>{
 useWorkflowStore.getState().addNode('wait',{x:0,y:0});render(<ConfigPanel selectedNodeId={useWorkflowStore.getState().nodes[0].id}/>);fireEvent.click(screen.getByTitle('展开配置面板'))
 await screen.findByText('此节点尚未提供必填字段规则，请核对配置。')
 request.mockResolvedValue(Response.json({...metadata,coveredModules:[...metadata.coveredModules,'wait']}))
 act(()=>window.dispatchEvent(new Event('studio:connection-restored')))
 await waitFor(()=>expect(screen.queryByText('此节点尚未提供必填字段规则，请核对配置。')).toBeNull())
 expect(screen.queryByRole('alert')).toBeNull()
})
it('installs the first endpoint before notifying a mounted service consumer',async()=>{
 vi.resetModules()
 const connection=await import('../api/config')
 const metadataApi=await import('../lib/requiredFields')
 await expect(metadataApi.fetchRequiredFields()).rejects.toThrow('not been configured')
 let result:Promise<unknown>|undefined
 const refresh=()=>{result=metadataApi.fetchRequiredFields()}
 window.addEventListener('studio:transport-changed',refresh)
 const restore=connection.configureStudioConnection('http://first-connection.invalid',request)
 try { expect(await result).toEqual(metadata);expect(request).toHaveBeenCalledOnce() }
 finally {window.removeEventListener('studio:transport-changed',refresh);restore()}
})
