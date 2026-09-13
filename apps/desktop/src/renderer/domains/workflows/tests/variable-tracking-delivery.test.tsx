import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {VariableTrackingPanel} from '../components/VariableTrackingPanel'
import {configureStudioConnection} from '../api/config'
import {variableTrackingApi} from '../api'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
const record={timestamp:'2026-09-14T00:00:00Z',variable_name:'result',old_value:null,new_value:'已确认值',node_id:'node',node_name:'脚本',operation:'create',value_type:'string'}
const list=(value:Omit<typeof record,'new_value'> & {new_value:unknown}=record)=>Response.json({tracking:[value],count:1})
let restore:()=>void=()=>{}
afterEach(()=>{cleanup();restore()})
const panel=(workflowId='workflow',isOpen=true)=><VariableTrackingPanel workflowId={workflowId} isOpen={isOpen} onClose={vi.fn()}/>
it('keeps records and reports a rejected clear, then clears only after confirmation',async()=>{
 let fail=true
 restore=configureStudioConnection('http://tracking.test',async(_url,init)=>init?.method==='DELETE'?fail?Response.json({detail:'磁盘错误'},{status:507}):Response.json({message:'变量追踪记录已清空'}):list())
 render(panel());await screen.findByText('已确认值');fireEvent.click(screen.getByTitle('关闭自动刷新'))
 fireEvent.click(screen.getByTitle('清空记录'));await screen.findByRole('alert');expect(screen.getByText('已确认值')).toBeTruthy();expect(screen.getByRole('alert').textContent).toContain('磁盘错误')
 fail=false;fireEvent.click(screen.getByTitle('清空记录'));await waitFor(()=>expect(screen.queryByText('已确认值')).toBeNull());expect(screen.queryByRole('alert')).toBeNull()
})
it('ignores an older read after clearing and prevents duplicate clear requests',async()=>{
 let readCount=0;let finishRead!:(value:Response)=>void;let finishClear!:(value:Response)=>void;let clears=0
 restore=configureStudioConnection('http://tracking.test',async(_url,init)=>{
  if(init?.method==='DELETE'){clears++;return new Promise(resolve=>{finishClear=resolve})}
  if(++readCount===1)return list()
  return new Promise(resolve=>{finishRead=resolve})
 })
 render(panel());await screen.findByText('已确认值');fireEvent.click(screen.getByTitle('关闭自动刷新'));fireEvent.click(screen.getByTitle('手动刷新'))
 await waitFor(()=>expect(finishRead).toBeTypeOf('function'));fireEvent.click(screen.getByTitle('清空记录'));fireEvent.click(screen.getByTitle('清空记录'))
 await waitFor(()=>expect(clears).toBe(1));expect(screen.getByRole('status').textContent).toContain('等待服务确认')
 await act(async()=>finishClear(Response.json({message:'已清空'})));await waitFor(()=>expect(screen.queryByText('已确认值')).toBeNull())
 await act(async()=>finishRead(list()));expect(screen.queryByText('已确认值')).toBeNull()
})
it.each(['document','close'] as const)('ignores late records after %s changes',async action=>{
 let finish!:(value:Response)=>void
 restore=configureStudioConnection('http://tracking.test',async url=>String(url).includes('/old/')?new Promise(resolve=>{finish=resolve}):list({...record,new_value:'当前流程值'}))
 const view=render(panel('old'));await waitFor(()=>expect(finish).toBeTypeOf('function'))
 view.rerender(action==='close'?panel('old',false):panel('new'))
 if(action==='document')await screen.findByText('当前流程值')
 await act(async()=>finish(list()));expect(screen.queryByText('已确认值')).toBeNull()
})
it('retains confirmed records on malformed refresh and recovers on a later valid response',async()=>{
 let malformed=false
 restore=configureStudioConnection('http://tracking.test',async()=>malformed?Response.json({tracking:[null],count:1}):list())
 render(panel());await screen.findByText('已确认值');fireEvent.click(screen.getByTitle('关闭自动刷新'));malformed=true;fireEvent.click(screen.getByTitle('手动刷新'))
 await screen.findByRole('alert');expect(screen.getByText('已确认值')).toBeTruthy()
 malformed=false;fireEvent.click(screen.getByTitle('手动刷新'));await waitFor(()=>expect(screen.queryByRole('alert')).toBeNull())
})
it('does not overlap refresh requests and still loads when reopened',async()=>{
 let finish!:(value:Response)=>void;let reads=0
 restore=configureStudioConnection('http://tracking.test',async()=>{reads++;return new Promise(resolve=>{finish=resolve})})
 const view=render(panel());await waitFor(()=>expect(reads).toBe(1));fireEvent.click(screen.getByTitle('手动刷新'));expect(reads).toBe(1)
 await act(async()=>finish(list()));fireEvent.click(screen.getByTitle('关闭自动刷新'));view.rerender(panel('workflow',false));view.rerender(panel());await waitFor(()=>expect(reads).toBe(2))
 await act(async()=>finish(list()));expect(screen.getByText('已确认值')).toBeTruthy()
})
it.each(['memory','http'] as const)('uses the same tracking read/clear wire contract over %s',async mode=>{
 vi.resetModules();const mock=await import('../api/mock-server');const server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null
 restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
 try{
  expect(await variableTrackingApi.list('tracking')).toMatchObject({success:true,data:{tracking:[],count:0}})
  expect(await variableTrackingApi.clear('tracking')).toMatchObject({success:true,data:{message:'变量追踪记录已清空'}})
  const result=await (server?fetch:mock.mockRequest)(`${server?.origin??'http://autoflow-studio.mock'}/api/workflows/tracking/variable-tracking`,{method:'POST'})
  expect(result.status).toBe(405)
 }finally{mock.configureMock({disconnect:true});await server?.close()}
})
it.each([null,{tracking:[]},{tracking:[],count:1},{tracking:[{...record,operation:'delete'}],count:1}])('rejects malformed tracking payload %j',async value=>{
 restore=configureStudioConnection('http://tracking.test',async()=>Response.json(value));expect(await variableTrackingApi.list('workflow')).toMatchObject({success:false,error:'变量追踪响应格式错误，保留最后确认记录'})
})
it('requires a clear acknowledgement and encodes workflow identifiers',async()=>{
 const requests:string[]=[]
 restore=configureStudioConnection('http://tracking.test',async url=>{requests.push(String(url));return Response.json({})})
 expect(await variableTrackingApi.clear('a/b?c')).toMatchObject({success:false});expect(requests[0]).toContain('/workflows/a%2Fb%3Fc/variable-tracking')
})

it('ignores a clear response from the previously displayed workflow',async()=>{
 let finish!:(value:Response)=>void
 restore=configureStudioConnection('http://tracking.test',async(url,init)=>init?.method==='DELETE'?new Promise(resolve=>{finish=resolve}):list({...record,new_value:String(url).includes('/new/')?'新流程记录':'旧流程记录'}))
 const view=render(panel('old'));await screen.findByText('旧流程记录');fireEvent.click(screen.getByTitle('清空记录'));await waitFor(()=>expect(finish).toBeTypeOf('function'))
 view.rerender(panel('new'));await screen.findByText('新流程记录');await act(async()=>finish(Response.json({message:'已清空'})))
 expect(screen.getByText('新流程记录')).toBeTruthy()
})

it('searches nested JSON values and distinguishes filtered emptiness',async()=>{
 restore=configureStudioConnection('http://tracking.test',async()=>list({...record,new_value:{nested:['前端脚本验收']}}))
 render(panel());await screen.findByText(/"前端脚本验收"/)
 const search=screen.getByPlaceholderText('搜索变量名、模块名或值...')
 fireEvent.change(search,{target:{value:'前端脚本验收'}});expect(screen.getByText(/"前端脚本验收"/)).toBeTruthy()
 fireEvent.change(search,{target:{value:'未命中'}});expect(screen.getByText('没有匹配的追踪记录')).toBeTruthy();expect(screen.queryByText('运行工作流后将显示变量变化')).toBeNull()
})
it('shows a null previous value when updating a variable',async()=>{
 restore=configureStudioConnection('http://tracking.test',async()=>list({...record,operation:'update'}))
 render(panel());await screen.findByText('旧值');expect(screen.getByText('null')).toBeTruthy()
})
