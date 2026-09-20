import {getStudioTransportRevision} from './transport'
import {apiRequest, type ApiResponse} from '../api'
import {isMcpCommandLookup,isMcpConfigResponse,isMcpStatus,isMcpSaved,isMcpReloaded,type McpConfig} from '../lib/mcpContract'
async function checked<T>(response:Promise<ApiResponse<unknown>>,valid:(value:unknown)=>value is T,error='MCP 配置或状态响应格式错误'):Promise<ApiResponse<T>> {
  const revision=getStudioTransportRevision()
  const result=await response
  if(revision!==getStudioTransportRevision())return {success:false,error:'服务连接已变更，MCP 操作结果未应用'}
  if(!result.success)return {...result,data:undefined}
  if(!valid(result.data))return {success:false,error}
  return {...result,data:result.data}
}
const pending=new Map<string,string>()
const commandId=(key:string)=>{const current=pending.get(key);if(current)return current;const id=crypto.randomUUID();pending.set(key,id);return id}
async function command<T>(key:string,path:string,body:Record<string,unknown>,valid:(value:unknown)=>value is T,error?:string):Promise<ApiResponse<T>>{
  const id=commandId(key)
  const direct=await checked(apiRequest(path,{method:path.endsWith('/config')?'PUT':'POST',body:JSON.stringify({...body,commandId:id})}),valid,error)
  if(direct.success || (direct.httpStatus!==undefined && direct.httpStatus<500)){pending.delete(key);return direct}
  const recovered=await checked(apiRequest(`/ai-assistant/mcp/commands/${encodeURIComponent(id)}`),isMcpCommandLookup)
  if(recovered.success && recovered.data && valid(recovered.data)){pending.delete(key);return {...recovered,data:recovered.data as T}}
  return direct
}
export const mcpApi={
  config:()=>checked(apiRequest('/ai-assistant/mcp/config'),isMcpConfigResponse),
  status:()=>checked(apiRequest('/ai-assistant/mcp/status'),isMcpStatus),
  save:(config:McpConfig,expectedRevision=0)=>command(`save:${expectedRevision}:${JSON.stringify(config)}`,'/ai-assistant/mcp/config',{config,expectedRevision},isMcpSaved,'服务未确认配置已保存'),
  reload:(expectedRevision=0)=>command(`reload:${expectedRevision}`,'/ai-assistant/mcp/reload',{expectedRevision},isMcpReloaded),
}
