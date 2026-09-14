import { isRetentionConfig, retentionDefaults } from '../lib/retentionContract'
import {isMcpConfig, type McpConfig} from '../lib/mcpContract'
import {mcpFormTransport} from '../lib/mcpConfigText'
/** Local fixtures for retained settings forms; connection probes never contact remote services. */
const prefix = 'autoflow:studio:mock:settings:'
type Value = Record<string, unknown>
const read = (name: string, fallback: Value = {}): Value => JSON.parse(localStorage.getItem(prefix + name) || JSON.stringify(fallback))
const save = (name: string, value: Value) => localStorage.setItem(prefix + name, JSON.stringify(value))
const json = (value: unknown, status = 200) => Response.json(value, { status })
export function mockSettingsRequest(path: string, method: string, body: Value): Response | undefined {
  if (path === '/credentials' || path.startsWith('/credentials/')) {
    // Names are user data, including Object prototype property names.
    const credentials: Value = Object.assign(Object.create(null), read('credentials'))
    const fail = (error: string, status: number) => json({success:false,error},status)
    if (path === '/credentials/names' && method === 'GET') return json({success:true,names:Object.keys(credentials)})
    if (path === '/credentials' && method === 'GET') return json({success:true,credentials:Object.values(credentials),mock:true})
    if (path === '/credentials' && method === 'POST') {
      if (typeof body.name !== 'string' || !body.fields || typeof body.fields !== 'object' || Array.isArray(body.fields)
        || Object.values(body.fields).some(value => typeof value !== 'string')
        || (body.description != null && typeof body.description !== 'string')) return fail('凭据格式错误',422)
      const name = body.name.trim()
      if (!name || !Object.keys(body.fields).length) return fail('凭据名称和字段不能为空',400)
      const previous = credentials[name] as Value | undefined
      const existing = (previous?.fields ?? []) as Array<{key:string;masked:string}>
      const keys = [...new Set([...existing.map(field => field.key), ...Object.keys(body.fields)])]
      credentials[name] = {name,description:body.description || previous?.description || '',
        fields:keys.map(key => ({key,masked:'•••••• (Mock)'})),
        created_at:previous?.created_at || new Date().toISOString(),updated_at:new Date().toISOString()}
      // Match partial upsert semantics using metadata only; never retain secret values.
      save('credentials', credentials)
      return json({success:true,name,mock:true})
    }
    if (path === '/credentials/rename' && method === 'POST') {
      if (typeof body.old_name !== 'string' || typeof body.new_name !== 'string') return fail('凭据名称格式错误',422)
      const old = body.old_name.trim(), name = body.new_name.trim()
      if (!old || !name) return fail('凭据名称不能为空',400)
      if (!credentials[old]) return fail('凭据不存在',404)
      if (old !== name && credentials[name]) return fail('凭据名称已存在',409)
      credentials[name] = {...(credentials[old] as Value),name}
      if (old !== name) delete credentials[old]
      save('credentials',credentials)
      return json({success:true})
    }
    if (path.startsWith('/credentials/') && method === 'DELETE') {
      const name = path.slice('/credentials/'.length)
      if (!credentials[name]) return fail('凭据不存在',404)
      delete credentials[name]
      save('credentials',credentials)
      return json({success:true})
    }
    return fail('不支持的凭据操作',405)
  }
  if (path.startsWith('/retention/')) {
    const usage = {recordings:{count:0,sizeMB:0},data:{count:0,sizeMB:0}}
    const config = read('retention', retentionDefaults)
    if (path === '/retention/config' && method === 'GET') return json({success:true,mock:true,usage,config})
    if (path === '/retention/usage' && method === 'GET') return json({success:true,mock:true,usage})
    if (path === '/retention/config' && method === 'POST') {
      // Keep the old partial-update wire behavior, but never hide explicitly invalid values.
      const next = {...config,...Object.fromEntries(Object.entries(body).filter(([,value]) => value != null))}
      if (!isRetentionConfig(next)) return json({success:false,error:'留存策略必须使用合法整数，清理间隔至少为 1 小时'},422)
      try { save('retention',next) } catch { return json({success:false,error:'无法写入留存策略'},507) }
      return json({success:true,mock:true,config:next})
    }
    if (path === '/retention/cleanup' && method === 'POST') return json({success:true,mock:true,recordings:{removed:0,freedMB:0},data:{removed:0,freedMB:0}})
    return json({success:false,error:'不支持的留存操作'},405)
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
