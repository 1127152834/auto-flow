import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import {afterEach, expect, it, vi} from 'vitest'
import {MCPConfigPanel} from '../components/MCPConfigPanel'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
import {mockSettingsRequest} from '../api/mock-settings'
const config={mcpServers:{fixture:{transport:'stdio',command:'node',args:[],disabled:false}}}
const status={servers:[],total_tools_injected:0}
let restore=()=>{}
afterEach(()=>{cleanup();restore();vi.unstubAllGlobals()})
function setup(write:()=>Promise<Response>,read?:()=>Promise<Response>,reload?:()=>Promise<Response>){
 const calls:string[]=[]
 restore=configureStudioConnection('http://mcp.fixture',async(input,init)=>{
  const path=new URL(String(input)).pathname;calls.push(`${init?.method||'GET'} ${path}`)
  if(init?.method==='PUT')return write()
  if(path.endsWith('/reload'))return reload?reload():Response.json({success:true})
  if(path.endsWith('/status'))return Response.json(status)
  return read?read():Response.json(config)
 });return calls
}
it.each([503,200])('shows load failure instead of pretending there are no servers at HTTP %s',async code=>{
 setup(async()=>Response.json({success:true}),async()=>Response.json({success:false,error:'读取配置失败'},{status:code}))
 render(<MCPConfigPanel/>);expect(await screen.findByText(/读取配置失败/)).toBeTruthy()
 expect(screen.queryByText(/还没有配置 MCP/)).toBeNull()
})
it.each([503,200])('keeps confirmed enable state when saving fails at HTTP %s',async code=>{
 setup(async()=>Response.json({success:false,error:'测试磁盘不可写'},{status:code}))
 render(<MCPConfigPanel/>);fireEvent.click(await screen.findByRole('button',{name:'禁用'}))
 expect(await screen.findByText(/测试磁盘不可写/)).toBeTruthy()
 expect(screen.getByRole('button',{name:'禁用'})).toBeTruthy()
 expect(screen.queryByText('已保存')).toBeNull()
})
it('retains new server input on rejected save and supports retry',async()=>{
 let rejected=true
 setup(async()=>Response.json(rejected?{success:false,error:'保存被拒绝'}:{success:true,saved:true}))
 render(<MCPConfigPanel/>);await screen.findByText('fixture')
 fireEvent.click(screen.getByRole('button',{name:'添加'}))
 fireEvent.change(screen.getByPlaceholderText('例如 filesystem / weather / github'),{target:{value:'draft'}})
 fireEvent.change(screen.getByPlaceholderText('例如 npx / node / python'),{target:{value:'node'}})
 fireEvent.click(screen.getByRole('button',{name:'保存'}))
 expect(await screen.findByText(/保存被拒绝/)).toBeTruthy()
 expect(screen.getByPlaceholderText('例如 filesystem / weather / github')).toHaveProperty('value','draft')
 expect(screen.queryByText('draft',{selector:'span'})).toBeNull()
 rejected=false;fireEvent.click(screen.getByRole('button',{name:'保存'}))
 await screen.findByText('draft',{selector:'span'})
 expect(screen.queryByPlaceholderText('例如 filesystem / weather / github')).toBeNull()
})
it('serializes pending save and does not update confirmed list before acknowledgement',async()=>{
 let resolve!:(value:Response)=>void
 const calls=setup(()=>new Promise<Response>(r=>{resolve=r}))
 render(<MCPConfigPanel/>);const button=await screen.findByRole('button',{name:'禁用'})
 fireEvent.click(button);fireEvent.click(button)
 await waitFor(()=>expect(calls.filter(call=>call.startsWith('PUT'))).toHaveLength(1))
 expect(button).toHaveProperty('disabled',true)
 expect(screen.queryByText('已禁用')).toBeNull()
 resolve(Response.json({success:true,saved:true}));await screen.findByRole('button',{name:'启用'})
})
it('does not reload or remove a server when deletion save fails',async()=>{
 const calls=setup(async()=>Response.json({success:false,error:'删除保存失败'}))
 render(<MCPConfigPanel/>);await screen.findByText('fixture')
 fireEvent.click(screen.getByRole('button',{name:'删除 MCP 服务器 fixture'}))
 fireEvent.click(await screen.findByRole('button',{name:'删除'}))
 await screen.findByText(/删除保存失败/)
 expect(screen.getByText('fixture')).toBeTruthy()
 expect(calls.some(call=>call.endsWith('/reload'))).toBe(false)
})
it('treats a named template as a new editable server and rejects duplicate names',async()=>{
 const calls=setup(async()=>Response.json({success:true,saved:true}))
 render(<MCPConfigPanel/>);await screen.findByText('fixture')
 fireEvent.click(screen.getByRole('button',{name:'推荐模板'}))
 fireEvent.click(screen.getByRole('button',{name:/通用 HTTP 抓取/}))
 const name=screen.getByPlaceholderText('例如 filesystem / weather / github')
 expect(name).toHaveProperty('disabled',false)
 fireEvent.change(name,{target:{value:'fixture'}})
 expect(screen.getByRole('button',{name:'保存'})).toHaveProperty('disabled',true)
 expect(calls.some(call=>call.startsWith('PUT'))).toBe(false)
})

it.each([null,[],{mcpServers:{bad:null}},{mcpServers:{bad:{args:1}}}])('rejects malformed config %# without rendering an empty success',async value=>{
 setup(async()=>Response.json({success:true}),async()=>Response.json(value))
 render(<MCPConfigPanel/>);await screen.findByText('MCP 配置或状态响应格式错误')
 expect(screen.queryByText(/还没有配置 MCP/)).toBeNull()
})
it('does not accept a successful HTTP response without a save acknowledgement',async()=>{
 setup(async()=>Response.json({}))
 render(<MCPConfigPanel/>);fireEvent.click(await screen.findByRole('button',{name:'禁用'}))
 await screen.findByText(/服务未确认配置已保存/)
 expect(screen.getByRole('button',{name:'禁用'})).toBeTruthy()
})

it('locks editable fields and cancel while a new server save is pending',async()=>{
 let resolve!:(value:Response)=>void
 setup(()=>new Promise<Response>(r=>{resolve=r}))
 render(<MCPConfigPanel/>);await screen.findByText('fixture')
 fireEvent.click(screen.getByRole('button',{name:'添加'}))
 const name=screen.getByPlaceholderText('例如 filesystem / weather / github')
 fireEvent.change(name,{target:{value:'pending'}})
 fireEvent.change(screen.getByPlaceholderText('例如 npx / node / python'),{target:{value:'node'}})
 fireEvent.click(screen.getByRole('button',{name:'保存'}))
 await waitFor(()=>expect(name.closest('fieldset')).toHaveProperty('disabled',true))
 expect(screen.getByRole('button',{name:'取消'})).toHaveProperty('disabled',true)
 resolve(Response.json({success:false,error:'保存失败可重试'}))
 await screen.findByText(/保存失败可重试/)
 expect(name.closest('fieldset')).toHaveProperty('disabled',false)
 expect(name).toHaveProperty('value','pending')
})
it.each(['memory','http'] as const)('saves and reloads a complete MCP form through %s without pretending to connect',async mode=>{
 const data=new Map<string,string>()
 vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})
 const request=async(input:RequestInfo|URL,init?:RequestInit)=>{
  const req=input instanceof Request?input:new Request(input,init)
  const path=new URL(req.url).pathname.replace(/^\/api/,'')
  return mockSettingsRequest(path,req.method,req.method==='PUT'?await req.json():{}) || Response.json({success:false},{status:404})
 }
 const server=mode==='http'?await startHttpStudioFixture(request):null
 restore=configureStudioConnection(server?.origin||'http://mcp.fixture',server?fetch:request)
 try{
  const view=render(<MCPConfigPanel/>);await screen.findByText(/还没有配置 MCP/)
  fireEvent.click(screen.getByRole('button',{name:'添加'}))
  fireEvent.change(screen.getByPlaceholderText('例如 filesystem / weather / github'),{target:{value:'controlled'}})
  fireEvent.change(screen.getByPlaceholderText('例如 npx / node / python'),{target:{value:'node'}})
  fireEvent.click(screen.getByRole('button',{name:'保存'}));await screen.findByText('controlled',{selector:'span'})
  view.unmount();render(<MCPConfigPanel/>);await screen.findByText('controlled',{selector:'span'})
  expect(screen.getByText('未连接')).toBeTruthy()
  expect(JSON.parse(localStorage.getItem('autoflow:studio:mock:settings:mcp')!).mcpServers.controlled.command).toBe('node')
 }finally{cleanup();await server?.close();localStorage.removeItem('autoflow:studio:mock:settings:mcp')}
})

it('retries a failed initial read before enabling configuration writes',async()=>{
 let failed=true
 setup(async()=>Response.json({success:true,saved:true}),async()=>Response.json(failed?{success:false,error:'初次读取失败'}:config))
 render(<MCPConfigPanel/>);await screen.findByText(/初次读取失败/)
 expect(screen.getByRole('button',{name:'添加'})).toHaveProperty('disabled',true)
 failed=false;fireEvent.click(screen.getByRole('button',{name:'重新读取配置'}))
 await screen.findByText('fixture')
 expect(screen.getByRole('button',{name:'添加'})).toHaveProperty('disabled',false)
})
it('keeps the confirmed list and error when reload is rejected in HTTP 200',async()=>{
 const calls=setup(async()=>Response.json({success:true,saved:true}),undefined,async()=>Response.json({success:false,error:'重连被拒绝'}))
 render(<MCPConfigPanel/>);await screen.findByText('fixture')
 fireEvent.click(screen.getByRole('button',{name:'重新连接'}));await screen.findByText(/重连失败：重连被拒绝/)
 expect(screen.getByText('fixture')).toBeTruthy()
 expect(calls.filter(call=>call==='GET /api/ai-assistant/mcp/config')).toHaveLength(1)
})
