import type {components} from '../../../shared/api/generated'
// The generator materializes defaulted fields; source MCP files may omit every server option.
export type McpServerConfig = Partial<components['schemas']['StudioMcpServerConfig']>
export type McpConfig = Omit<components['schemas']['StudioMcpConfig'],'mcpServers'> & {mcpServers:Record<string,McpServerConfig>}
export type McpConfigResponse = Omit<components['schemas']['StudioMcpConfigResponse'],'mcpServers'> & {mcpServers:Record<string,McpServerConfig>}
export type McpStatus = components['schemas']['StudioMcpStatus']
export type McpSaved = components['schemas']['StudioMcpSaved']
export type McpReloaded = components['schemas']['StudioMcpReloaded']
export type McpCommandLookup = components['schemas']['StudioMcpCommandLookup']
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(item => typeof item === 'string')
const stringMap = (value: unknown) => object(value) && Object.values(value).every(item => typeof item === 'string')
const count = (value: unknown) => Number.isSafeInteger(value) && Number(value) >= 0
export function isMcpConfig(value: unknown): value is McpConfig {
  return object(value) && object(value.mcpServers) && Object.entries(value.mcpServers).every(([name, server]) =>
    !!name.trim() && object(server) &&
    (server.transport == null || typeof server.transport === 'string' && ['', 'stdio','sse','http','streamable_http','streamable-http'].includes(server.transport.toLowerCase())) &&
    ['command','cwd','url'].every(key => server[key] == null || typeof server[key] === 'string') &&
    ['args','autoApprove'].every(key => server[key] == null || strings(server[key])) &&
    ['env','headers'].every(key => server[key] == null || stringMap(server[key])) &&
    (server.disabled == null || typeof server.disabled === 'boolean'))
}
export function isMcpConfigResponse(value: unknown): value is McpConfigResponse {
  return isMcpConfig(value) && count((value as Record<string, unknown>).revision)
}
export function isMcpStatus(value: unknown): value is McpStatus {
  return object(value) && count(value.total_tools_injected) &&
    Array.isArray(value.servers) && value.servers.every(server => object(server) &&
      typeof server.name === 'string' && typeof server.transport === 'string' &&
      typeof server.disabled === 'boolean' && typeof server.connected === 'boolean' && count(server.tool_count) &&
      (server.last_error === null || typeof server.last_error === 'string') &&
      (server.connected_at === null || typeof server.connected_at === 'string') && strings(server.auto_approve) &&
      Array.isArray(server.tools) && server.tools.every(tool => object(tool) && typeof tool.name === 'string' && typeof tool.description === 'string'))
}
export function isMcpSaved(value: unknown): value is McpSaved {
  return object(value) && value.success === true && value.saved === true &&
    typeof value.commandId === 'string' && !!value.commandId && Number.isSafeInteger(value.revision) && Number(value.revision) >= 1
}
export function isMcpReloaded(value: unknown): value is McpReloaded {
  return object(value) && count(value.total_servers) && count(value.revision) && typeof value.commandId === 'string' && !!value.commandId && strings(value.disabled) &&
    Array.isArray(value.connected) && value.connected.every(server => object(server) && typeof server.name === 'string' && typeof server.transport === 'string' && count(server.tool_count)) &&
    Array.isArray(value.failed) && value.failed.every(server => object(server) && typeof server.name === 'string' && typeof server.error === 'string')
}
export function isMcpCommandLookup(value: unknown): value is McpCommandLookup {
  return object(value) && typeof value.commandId === 'string' && !!value.commandId &&
    Number.isSafeInteger(value.httpStatus) && Number(value.httpStatus) >= 200 && Number(value.httpStatus) <= 599
}
