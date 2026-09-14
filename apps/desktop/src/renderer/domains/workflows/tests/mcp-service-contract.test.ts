import {afterEach,expect,it,vi} from 'vitest'
import {mcpApi} from '../api/mcp'
import {isMcpConfig,isMcpReloaded,isMcpStatus} from '../lib/mcpContract'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
import {mockSettingsRequest} from '../api/mock-settings'
let restore=()=>{}
afterEach(()=>{restore();vi.unstubAllGlobals()})
it.each([null,'','http','HTTP','streamable_http','Streamable-HTTP'])('accepts compatible transport case %# and nullable omitted values',transport=>{
 expect(isMcpConfig({mcpServers:{fixture:{transport,args:null,env:null,headers:null,autoApprove:null}},extension:1})).toBe(true)
})
it.each([null,{}, {servers:[],total_tools_injected:'0'}, {servers:[{}],total_tools_injected:0}])('rejects malformed status %#',value=>expect(isMcpStatus(value)).toBe(false))
it('distinguishes partial connection failure from invalid reload acknowledgement',()=>{
 expect(isMcpReloaded({connected:[],failed:[{name:'offline',error:'不可达'}],disabled:[],total_servers:1})).toBe(true)
 expect(isMcpReloaded({success:true})).toBe(false)
})
it.each(['memory','http'] as const)('uses the same persisted configuration and truthful reload/status contract over %s',async mode=>{
 const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value)})
 const handler=async(input:RequestInfo|URL,init?:RequestInit)=>{
  const req=input instanceof Request?input:new Request(input,init)
  return mockSettingsRequest(new URL(req.url).pathname.replace(/^\/api/,''),req.method,req.method==='PUT'?await req.json():{}) || Response.json({success:false},{status:404})
 }
 const server=mode==='http'?await startHttpStudioFixture(handler):null
 restore=configureStudioConnection(server?.origin||'http://mcp.fixture',server?fetch:handler)
 try{
  const config={mcpServers:{active:{command:'node',extensionSetting:{keep:true}},off:{command:'node',disabled:true}},extensionRoot:1}
  expect((await mcpApi.save(config)).success).toBe(true)
  expect((await mcpApi.config()).data).toEqual(config)
  const reload=await mcpApi.reload();expect(reload.success).toBe(true)
  expect(reload.data?.connected).toEqual([])
  expect(reload.data?.failed).toEqual([{name:'active',error:'Mock 未执行外部 MCP 连接'}])
  expect(reload.data?.disabled).toEqual(['off'])
  const status=await mcpApi.status();expect(status.success).toBe(true)
  expect(status.data?.servers.map(item=>[item.name,item.connected,item.disabled])).toEqual([['active',false,false],['off',false,true]])
  expect(status.data?.total_tools_injected).toBe(0)
 }finally{await server?.close()}
})

it.each([['/ai-assistant/mcp/config','POST'],['/ai-assistant/mcp/status','PUT'],['/ai-assistant/mcp/reload','GET']])('rejects unsupported MCP method %s %s', (path,method)=>{
 const response=mockSettingsRequest(path,method,{})
 expect(response?.status).toBe(405)
})
it('rejects invalid configuration before touching persisted data',()=>{
 const setItem=vi.fn();vi.stubGlobal('localStorage',{getItem:()=>null,setItem})
 expect(mockSettingsRequest('/ai-assistant/mcp/config','PUT',{config:{mcpServers:{bad:null}}})?.status).toBe(422)
 expect(setItem).not.toHaveBeenCalled()
})
