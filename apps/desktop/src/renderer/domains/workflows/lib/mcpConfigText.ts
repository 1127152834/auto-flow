/** Parse only the visible MCP field; never discard malformed non-empty lines. */
export function parseMcpMapping(text: string, kind: 'env' | 'headers'): Record<string, string> {
  const delimiter = kind === 'env' ? '=' : ':'
  const label = kind === 'env' ? '环境变量' : '请求头'
  const entries: Array<[string, string]> = []
  const keys = new Set<string>()
  for (const [index, raw] of text.split(/\r?\n/).entries()) {
    const line = raw.trim()
    if (!line) continue
    const separator = line.indexOf(delimiter)
    const key = line.slice(0, separator).trim()
    if (separator < 1 || !key) throw new Error(`${label}第 ${index + 1} 行必须使用 ${kind === 'env' ? 'KEY=VALUE' : 'Key: Value'} 格式`)
    const value = line.slice(separator + 1).trim()
    if (key.includes('\0') || value.includes('\0')) throw new Error(`${label}第 ${index + 1} 行包含无效字符`)
    if (kind === 'headers') {
      try { new Headers([[key, value]]) } catch { throw new Error(`请求头第 ${index + 1} 行名称或值无效`) }
    }
    const identity = kind === 'headers' ? key.toLowerCase() : key
    if (keys.has(identity)) throw new Error(`${label}第 ${index + 1} 行与前面的键重复`)
    keys.add(identity)
    entries.push([key, value])
  }
  return Object.fromEntries(entries)
}

/** Match frozen mcp_manager's compatibility aliases and omitted transport inference. */
export function mcpFormTransport(server: {transport?: string | null; command?: string | null; url?: string | null}): 'stdio' | 'sse' | 'http' {
  const transport = server.transport?.toLowerCase()
  if (transport === 'streamable_http' || transport === 'streamable-http') return 'http'
  if (transport === 'stdio' || transport === 'sse' || transport === 'http') return transport
  if (server.command) return 'stdio'
  if (server.url) return server.url.toLowerCase().includes('sse') ? 'sse' : 'http'
  return 'stdio'
}
