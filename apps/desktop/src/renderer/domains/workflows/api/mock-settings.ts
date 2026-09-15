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
    const stored = read('credentials')
    const migrated = stored.version === 1 && stored.entries && stored.commands
    const credentials: Value = Object.assign(Object.create(null), migrated ? stored.entries : stored)
    const commands: Value = Object.assign(Object.create(null), migrated ? stored.commands : {})
    for (const [name, entry] of Object.entries(credentials)) {
      const value = entry as Value
      credentials[name] = { ...value, revision: Number.isSafeInteger(value.revision) && Number(value.revision) > 0 ? value.revision : 1 }
    }
    let revision = Math.max(Number(migrated ? stored.revision : 0) || 0, ...Object.values(credentials).map(entry => Number((entry as Value).revision)), 0)
    // One storage write commits metadata and command receipts together. No secret values enter this envelope.
    const persist = () => {
      try { save('credentials', { version: 1, revision, entries: credentials, commands }); return null }
      catch { return json({success:false,error:'无法写入凭据元数据'},507) }
    }
    const fail = (error: string, status: number) => json({success:false,error},status)
    if (path === '/credentials/names' && method === 'GET') return json({success:true,names:Object.keys(credentials)})
    if (path === '/credentials' && method === 'GET') return json({success:true,credentials:Object.values(credentials),mock:true})
    if (path === '/credentials/fields' && method === 'POST') {
      if (typeof body.commandId !== 'string' || !body.commandId.trim() || body.commandId.length > 128 || typeof body.name !== 'string' || !body.name
        || !Number.isSafeInteger(body.expectedRevision) || Number(body.expectedRevision) < 1 || !Array.isArray(body.operations) || !body.operations.length
        || Object.keys(body).some(key => !['commandId','name','expectedRevision','operations'].includes(key))) return fail('字段命令格式错误',422)
      const operations: Array<{kind:'rename'|'remove';key:string;newKey?:string}> = []
      for (const entry of body.operations) {
        if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return fail('字段操作格式错误',422)
        const op = entry as Value
        if (!['rename','remove'].includes(String(op.kind)) || typeof op.key !== 'string' || !op.key
          || Object.keys(op).some(key => !(op.kind === 'rename' ? ['kind','key','newKey'] : ['kind','key']).includes(key))
          || (op.kind === 'rename' && (typeof op.newKey !== 'string' || !op.newKey.trim() || op.newKey !== op.newKey.trim()))) return fail('字段操作格式错误',422)
        operations.push(op.kind === 'rename' ? {kind:'rename',key:op.key,newKey:op.newKey as string} : {kind:'remove',key:op.key})
      }
      const fingerprint = JSON.stringify({name:body.name,expectedRevision:body.expectedRevision,operations})
      const previous = commands[body.commandId] as {fingerprint:string;response:unknown} | undefined
      if (previous) return previous.fingerprint === fingerprint ? json(previous.response) : fail('命令标识已用于其他修改',409)
      const credential = credentials[body.name] as Value | undefined
      if (!credential) return fail('凭据不存在',404)
      if (credential.revision !== body.expectedRevision) return fail('凭据已被修改，请重新读取后编辑字段',409)
      const fields = credential.fields as Array<{key:string;masked:string}>
      const keys = new Set(fields.map(field => field.key))
      if (new Set(operations.map(op => op.key)).size !== operations.length) return fail('同一字段不能重复修改',409)
      if (operations.some(op => !keys.has(op.key))) return fail('字段不存在',409)
      // All source/target validation precedes mutation; an occupied target is a conflict even if removed in this batch.
      if (operations.some(op => op.kind === 'rename' && op.newKey !== op.key && keys.has(op.newKey!))) return fail('目标字段已存在',409)
      const next = fields.flatMap(field => {
        const op = operations.find(item => item.key === field.key)
        return op?.kind === 'remove' ? [] : [{...field,key:op?.newKey ?? field.key}]
      })
      if (!next.length) return fail('至少需要一个字段',400)
      if (new Set(next.map(field => field.key)).size !== next.length) return fail('目标字段重复',409)
      const updated = {...credential,fields:next,revision:++revision,updated_at:new Date().toISOString()}
      const response = {success:true,commandId:body.commandId,credential:updated,mock:true}
      credentials[body.name] = updated
      commands[body.commandId] = {fingerprint,response}
      return persist() ?? json(response)
    }
    if (path === '/credentials' && method === 'POST') {
      if (typeof body.name !== 'string' || !body.fields || typeof body.fields !== 'object' || Array.isArray(body.fields)
        || Object.values(body.fields).some(value => typeof value !== 'string')
        || (body.description != null && typeof body.description !== 'string')) return fail('凭据格式错误',422)
      const name = body.name.trim()
      if (!name || !Object.keys(body.fields).length) return fail('凭据名称和字段不能为空',400)
      const previous = credentials[name] as Value | undefined
      const existing = (previous?.fields ?? []) as Array<{key:string;masked:string}>
      const keys = [...new Set([...existing.map(field => field.key), ...Object.keys(body.fields)])]
      credentials[name] = {name,revision:++revision,description:body.description || previous?.description || '',
        fields:keys.map(key => ({key,masked:'•••••• (Mock)'})),
        created_at:previous?.created_at || new Date().toISOString(),updated_at:new Date().toISOString()}
      // Match partial upsert semantics using metadata only; never retain secret values.
      const error = persist(); if (error) return error
      return json({success:true,name,mock:true})
    }
    if (path === '/credentials/rename' && method === 'POST') {
      if (typeof body.old_name !== 'string' || typeof body.new_name !== 'string') return fail('凭据名称格式错误',422)
      const old = body.old_name.trim(), name = body.new_name.trim()
      if (!old || !name) return fail('凭据名称不能为空',400)
      if (!credentials[old]) return fail('凭据不存在',404)
      if (old !== name && credentials[name]) return fail('凭据名称已存在',409)
      credentials[name] = {...(credentials[old] as Value),name,revision:++revision}
      if (old !== name) delete credentials[old]
      const error = persist(); if (error) return error
      return json({success:true})
    }
    if (path.startsWith('/credentials/') && method === 'DELETE') {
      const name = path.slice('/credentials/'.length)
      if (!credentials[name]) return fail('凭据不存在',404)
      delete credentials[name]
      const error = persist(); if (error) return error
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
