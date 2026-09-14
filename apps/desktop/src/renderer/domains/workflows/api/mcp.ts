import {getStudioTransportRevision} from './transport'
import {apiRequest, type ApiResponse} from '../api'
import {isMcpConfig,isMcpStatus,isMcpSaved,isMcpReloaded,type McpConfig} from '../lib/mcpContract'
async function checked<T>(response:Promise<ApiResponse<unknown>>,valid:(value:unknown)=>value is T,error='MCP 配置或状态响应格式错误'):Promise<ApiResponse<T>> {
  const revision=getStudioTransportRevision()
  const result=await response
  if(revision!==getStudioTransportRevision())return {success:false,error:'服务连接已变更，MCP 操作结果未应用'}
  if(!result.success)return {...result,data:undefined}
  if(!valid(result.data))return {success:false,error}
  return {...result,data:result.data}
}
export const mcpApi={
  config:()=>checked(apiRequest('/ai-assistant/mcp/config'),isMcpConfig),
  status:()=>checked(apiRequest('/ai-assistant/mcp/status'),isMcpStatus),
  save:(config:McpConfig)=>checked(apiRequest('/ai-assistant/mcp/config',{method:'PUT',body:JSON.stringify({config})}),isMcpSaved,'服务未确认配置已保存'),
  reload:()=>checked(apiRequest('/ai-assistant/mcp/reload',{method:'POST'}),isMcpReloaded),
}
