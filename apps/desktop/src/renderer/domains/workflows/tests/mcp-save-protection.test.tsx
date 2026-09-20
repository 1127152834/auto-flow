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
function setup(write:(body:unknown)=>Promise<Response>,read?:()=>Promise<Response>,reload?:()=>Promise<Response>){
 const calls:string[]=[]
 restore=configureStudioConnection('http://mcp.fixture',async(input,init)=>{
  const path=new URL(String(input)).pathname;calls.push(`${init?.method||'GET'} ${path}`)
  if(init?.method==='PUT')return write(JSON.parse(String(init.body)))
  if(path.endsWith('/reload'))return reload?reload():Response.json({success:true})
  if(path.endsWith('/status'))return Response.json(status)
  return read?read():Response.json({...config,revision:0})
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
 setup(async()=>Response.json(rejected?{success:false,error:'保存被拒绝'}:{success:true,saved:true,commandId:'save',revision:1}))
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
 resolve(Response.json({success:true,saved:true,commandId:'save',revision:1}));await screen.findByRole('button',{name:'启用'})
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
 const calls=setup(async()=>Response.json({success:true,saved:true,commandId:'save',revision:1}))
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
  return mockSettingsRequest(path,req.method,['PUT','POST'].includes(req.method)?await req.json():{}) || Response.json({success:false},{status:404})
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
  expect(JSON.parse(localStorage.getItem('autoflow:studio:mock:settings:mcp-state')!).config.mcpServers.controlled.command).toBe('node')
 }finally{cleanup();await server?.close();localStorage.removeItem('autoflow:studio:mock:settings:mcp-state')}
})

it('retries a failed initial read before enabling configuration writes',async()=>{
 let failed=true
 setup(async()=>Response.json({success:true,saved:true,commandId:'save',revision:1}),async()=>Response.json(failed?{success:false,error:'初次读取失败'}:{...config,revision:0}))
 render(<MCPConfigPanel/>);await screen.findByText(/初次读取失败/)
 expect(screen.getByRole('button',{name:'添加'})).toHaveProperty('disabled',true)
 failed=false;fireEvent.click(screen.getByRole('button',{name:'重新读取配置'}))
 await screen.findByText('fixture')
 expect(screen.getByRole('button',{name:'添加'})).toHaveProperty('disabled',false)
})
it('keeps the confirmed list and error when reload is rejected in HTTP 200',async()=>{
 const calls=setup(async()=>Response.json({success:true,saved:true,commandId:'save',revision:1}),undefined,async()=>Response.json({success:false,error:'重连被拒绝'}))
 render(<MCPConfigPanel/>);await screen.findByText('fixture')
 fireEvent.click(screen.getByRole('button',{name:'重新连接'}));await screen.findByText(/重连失败：重连被拒绝/)
 expect(screen.getByText('fixture')).toBeTruthy()
 expect(calls.filter(call=>call==='GET /api/ai-assistant/mcp/config')).toHaveLength(1)
})

it.each(['stdio','http','sse'] as const)('rejects malformed visible %s mapping before sending the form',async transport=>{
 const calls=setup(async()=>Response.json({success:true,saved:true,commandId:'save',revision:1}))
 render(<MCPConfigPanel/>);await screen.findByText('fixture')
 fireEvent.click(screen.getByRole('button',{name:'添加'}))
 fireEvent.change(screen.getByPlaceholderText('例如 filesystem / weather / github'),{target:{value:'text-check'}})
 fireEvent.click(screen.getByRole('button',{name:transport}))
 if(transport==='stdio')fireEvent.change(screen.getByPlaceholderText('例如 npx / node / python'),{target:{value:'node'}})
 else fireEvent.change(screen.getByPlaceholderText(transport==='http'?'https://example.com/mcp':'https://example.com/sse'),{target:{value:'https://fixture.invalid/mcp'}})
 const field=screen.getByRole('textbox',{name:transport==='stdio'?'环境变量':'请求头'})
 fireEvent.change(field,{target:{value:'BAD LINE'}})
 fireEvent.click(screen.getByRole('button',{name:'保存'}))
 await screen.findByText(/第 1 行必须使用/)
 expect(field).toHaveProperty('value','BAD LINE')
 expect(calls.some(call=>call.startsWith('PUT'))).toBe(false)
})
it('does not let a hidden invalid stdio field block a valid http submission',async()=>{
 const calls=setup(async()=>Response.json({success:true,saved:true,commandId:'save',revision:1}))
 render(<MCPConfigPanel/>);await screen.findByText('fixture');fireEvent.click(screen.getByRole('button',{name:'添加'}))
 fireEvent.change(screen.getByPlaceholderText('例如 filesystem / weather / github'),{target:{value:'switch-check'}})
 fireEvent.change(screen.getByRole('textbox',{name:'环境变量'}),{target:{value:'BAD LINE'}})
 fireEvent.click(screen.getByRole('button',{name:'http'}))
 fireEvent.change(screen.getByPlaceholderText('https://example.com/mcp'),{target:{value:'https://fixture.invalid/mcp'}})
 fireEvent.click(screen.getByRole('button',{name:'保存'}));await screen.findByText('switch-check',{selector:'span'})
 expect(calls.filter(call=>call.startsWith('PUT'))).toHaveLength(1)
})
it.each(['streamable_http','streamable-http'])('reads legacy %s transport without rewriting until explicit save',async transport=>{
 const calls=setup(async()=>Response.json({success:true,saved:true,commandId:'save',revision:1}),async()=>Response.json({mcpServers:{legacy:{transport,url:'https://fixture.invalid/mcp'}},revision:0}))
 render(<MCPConfigPanel/>);await screen.findByText('legacy');fireEvent.click(screen.getByRole('button',{name:'编辑'}))
 expect(screen.getByPlaceholderText('https://example.com/mcp')).toHaveProperty('value','https://fixture.invalid/mcp')
 expect(calls.some(call=>call.startsWith('PUT'))).toBe(false)
})

it.each(['not-a-url','file:///tmp/mcp'])('rejects invalid remote URL case %# without losing the input',async url=>{
 const calls=setup(async()=>Response.json({success:true,saved:true,commandId:'save',revision:1}))
 render(<MCPConfigPanel/>);await screen.findByText('fixture');fireEvent.click(screen.getByRole('button',{name:'添加'}))
 fireEvent.change(screen.getByPlaceholderText('例如 filesystem / weather / github'),{target:{value:'url-check'}})
 fireEvent.click(screen.getByRole('button',{name:'http'}))
 const input=screen.getByPlaceholderText('https://example.com/mcp');fireEvent.change(input,{target:{value:url}})
 fireEvent.click(screen.getByRole('button',{name:'保存'}));await screen.findByText('服务器 URL 必须是有效的 HTTP 或 HTTPS 地址')
 expect(input).toHaveProperty('value',url)
 expect(calls.some(call=>call.startsWith('PUT'))).toBe(false)
})
it('saves a prototype-like server name as an own JSON field',async()=>{
 let payload:unknown
 const calls=setup(async body=>{payload=body;return Response.json({success:true,saved:true,commandId:'save',revision:1})})
 render(<MCPConfigPanel/>);await screen.findByText('fixture');fireEvent.click(screen.getByRole('button',{name:'添加'}))
 fireEvent.change(screen.getByPlaceholderText('例如 filesystem / weather / github'),{target:{value:'__proto__'}})
 fireEvent.change(screen.getByPlaceholderText('例如 npx / node / python'),{target:{value:'node'}})
 fireEvent.click(screen.getByRole('button',{name:'保存'}));await screen.findByText('__proto__',{selector:'span'})
 expect(calls.filter(call=>call.startsWith('PUT'))).toHaveLength(1)
 expect(Object.hasOwn((payload as {config:{mcpServers:object}}).config.mcpServers,'__proto__')).toBe(true)
})

it('preserves root and server extensions when editing a supported field',async()=>{
 let payload:unknown
 setup(async body=>{payload=body;return Response.json({success:true,saved:true,commandId:'save',revision:1})},async()=>Response.json({mcpServers:{fixture:{command:'node',args:null,env:null,extensionSetting:{keep:42}}},extensionRoot:'keep',revision:0}))
 render(<MCPConfigPanel/>);await screen.findByText('fixture');fireEvent.click(screen.getByRole('button',{name:'编辑'}))
 fireEvent.change(screen.getByPlaceholderText('例如 npx / node / python'),{target:{value:'python'}})
 fireEvent.click(screen.getByRole('button',{name:'保存'}));await waitFor(()=>expect(payload).toBeTruthy())
 expect(payload).toMatchObject({config:{extensionRoot:'keep',mcpServers:{fixture:{command:'python',extensionSetting:{keep:42}}}}})
})
it('reports partial reload failures after refreshing server status',async()=>{
 setup(async()=>Response.json({success:true,saved:true,commandId:'save',revision:1}),undefined,async()=>Response.json({connected:[],failed:[{name:'fixture',error:'连接被拒绝'}],disabled:[],total_servers:1,commandId:'reload',revision:0}))
 render(<MCPConfigPanel/>);await screen.findByText('fixture');fireEvent.click(screen.getByRole('button',{name:'重新连接'}))
 await screen.findByText('部分 MCP 服务器连接失败：fixture：连接被拒绝')
 expect(screen.getByText('fixture')).toBeTruthy()
})
