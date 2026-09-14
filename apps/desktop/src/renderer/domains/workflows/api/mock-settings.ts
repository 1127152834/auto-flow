import {isMcpConfig, type McpConfig} from '../lib/mcpContract'
import {mcpFormTransport} from '../lib/mcpConfigText'
/** Local fixtures for retained settings forms; connection probes never contact remote services. */
const prefix = 'autoflow:studio:mock:settings:'
type Value = Record<string, unknown>
const read = (name: string, fallback: Value = {}): Value => JSON.parse(localStorage.getItem(prefix + name) || JSON.stringify(fallback))
const save = (name: string, value: Value) => localStorage.setItem(prefix + name, JSON.stringify(value))
const json = (value: unknown, status = 200) => Response.json(value, { status })
export function mockSettingsRequest(path: string, method: string, body: Value): Response | undefined {
  if (path === '/credentials/names') return json({success:true,names:Object.keys(read('credentials'))})
  if (path === '/credentials') {
    const credentials = read('credentials')
    if (method === 'POST') {
      const name = String(body.name || '').trim()
      if (!name) return json({success:false,error:'Credential name required'},400)
      const previous = credentials[name] as Value | undefined
      credentials[name] = {name,description:body.description || '',fields:Object.keys((body.fields || {}) as Value).map(key=>({key,masked:'•••••• (Mock)'})),created_at:previous?.created_at || new Date().toISOString(),updated_at:new Date().toISOString()}
      // The fixture retains names and masked field metadata, never credential values.
      save('credentials', credentials)
    }
    return json({success:true,credentials:Object.values(credentials),mock:true})
  }
  if (path === '/credentials/rename') {
    const credentials=read('credentials'), old=String(body.old_name), name=String(body.new_name)
    if (!credentials[old] || credentials[name]) return json({success:false,error:'Credential missing or name already exists'},409)
    credentials[name]={...(credentials[old] as Value),name};delete credentials[old];save('credentials',credentials);return json({success:true})
  }
  if (path.startsWith('/credentials/') && method === 'DELETE') {const credentials=read('credentials');delete credentials[path.split('/').at(-1)!];save('credentials',credentials);return json({success:true})}
  if (path.startsWith('/retention/')) {
    const usage={recordings:{count:0,sizeMB:0},data:{count:0,sizeMB:0}}
    if(path==='/retention/config' && method==='POST')save('retention',{...read('retention'),...body})
    return json({success:true,mock:true,usage,config:read('retention',{enabled:false,recordings_max_days:30,recordings_max_total_mb:0,data_max_days:30,data_max_total_mb:0,cleanup_interval_hours:24})})
  }
  if(path==='/local-workflows/webdav-config') {
    if(method==='POST')save('webdav',{...body,password:''})
    return json({success:true,config:read('webdav'),mock:true})
  }
  if(path==='/local-workflows/webdav-test')return json({success:false,error:'Mock 未执行 WebDAV 远程连接'})
  if(path==='/ai-assistant/mcp/config') {
    if(method==='PUT'){
      if(!isMcpConfig(body.config))return json({success:false,error:'MCP 配置格式错误'},422)
      save('mcp',body.config);return json({success:true,saved:true})
    }
    if(method!=='GET')return json({success:false,error:'不支持的配置操作'},405)
    return json(read('mcp',{mcpServers:{}}))
  }
  if(path==='/ai-assistant/mcp/status') {
    if(method!=='GET')return json({success:false,error:'状态只支持读取'},405)
    return json(read('mcp-status',{servers:[],total_tools_injected:0,mock:true}))
  }
  if(path==='/ai-assistant/mcp/reload') {
    if(method!=='POST')return json({success:false,error:'重连只支持 POST'},405)
    const config=read('mcp',{mcpServers:{}}) as McpConfig
    if(!isMcpConfig(config))return json({success:false,error:'MCP 配置格式错误'},422)
    const servers=Object.entries(config.mcpServers).map(([name,server])=>({
      name,transport:mcpFormTransport(server),disabled:server.disabled===true,connected:false,
      tool_count:0,tools:[],last_error:server.disabled?null:'Mock 未执行外部 MCP 连接',connected_at:null,auto_approve:server.autoApprove||[],
    }))
    save('mcp-status',{servers,total_tools_injected:0,mock:true})
    return json({connected:[],failed:servers.filter(server=>!server.disabled).map(server=>({name:server.name,error:server.last_error})),disabled:servers.filter(server=>server.disabled).map(server=>server.name),total_servers:servers.length,mock:true})
  }
  return undefined
}
