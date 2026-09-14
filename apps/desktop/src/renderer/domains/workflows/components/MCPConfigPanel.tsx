// Source: WebRPA@5ccb900e, components/workflow/MCPConfigPanel.tsx; see SOURCE.md for license and adaptation boundaries.
import { apiRequest } from '../api'
import { useEffect, useState, useCallback, useRef } from 'react'
import { Plus, Trash2, RefreshCw, CheckCircle2, XCircle, Server, AlertCircle, Loader2, ChevronRight, ChevronDown, ExternalLink, Sparkles, Search, Star } from 'lucide-react'
import { Button } from './controls/button'
import { Input } from './controls/input'
import { Label } from './controls/label'
import { useConfirm } from './controls/confirm-dialog'
import { MCP_TEMPLATES, TEMPLATE_CATEGORIES, type MCPTemplate } from './mcpTemplates'

/**
 * MCP（Model Context Protocol）配置面板
 *
 * 功能：
 * - 列出已配置的 MCP server，显示连接状态和工具数量
 * - 添加 / 编辑 / 删除 server（支持 stdio / sse / http 三种 transport）
 * - 一键重新连接
 * - 查看每个 server 暴露的工具列表
 */

interface MCPServerConfig {
  transport?: 'stdio' | 'sse' | 'http'
  command?: string
  args?: string[]
  env?: Record<string, string>
  cwd?: string
  url?: string
  headers?: Record<string, string>
  disabled?: boolean
  autoApprove?: string[]
}

interface MCPServerStatus {
  name: string
  transport: string
  disabled: boolean
  connected: boolean
  tool_count: number
  tools: { name: string; description: string }[]
  last_error: string | null
  connected_at: string | null
  auto_approve: string[]
}

interface MCPStatus {
  servers: MCPServerStatus[]
  total_tools_injected: number
}

const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(item => typeof item === 'string')
const stringMap = (value: unknown) => object(value) && Object.values(value).every(item => typeof item === 'string')
function validConfig(value: unknown): value is {mcpServers:Record<string,MCPServerConfig>} {
  return object(value) && object(value.mcpServers) && Object.entries(value.mcpServers).every(([name, server]) =>
    !!name.trim() && object(server) &&
    (server.transport === undefined || ['stdio','sse','http'].includes(String(server.transport))) &&
    ['command','cwd','url'].every(key => server[key] === undefined || typeof server[key] === 'string') &&
    ['args','autoApprove'].every(key => server[key] === undefined || strings(server[key])) &&
    ['env','headers'].every(key => server[key] === undefined || stringMap(server[key])) &&
    (server.disabled === undefined || typeof server.disabled === 'boolean'))
}
function validStatus(value: unknown): value is MCPStatus {
  return object(value) && Number.isSafeInteger(value.total_tools_injected) && Number(value.total_tools_injected) >= 0 &&
    Array.isArray(value.servers) && value.servers.every(server => object(server) &&
      typeof server.name === 'string' && typeof server.transport === 'string' &&
      typeof server.disabled === 'boolean' && typeof server.connected === 'boolean' &&
      Number.isSafeInteger(server.tool_count) && Number(server.tool_count) >= 0 &&
      (server.last_error === null || typeof server.last_error === 'string') &&
      (server.connected_at === null || typeof server.connected_at === 'string') && strings(server.auto_approve) &&
      Array.isArray(server.tools) && server.tools.every(tool => object(tool) && typeof tool.name === 'string' && typeof tool.description === 'string'))
}

const DEFAULT_NEW_SERVER: MCPServerConfig = {
  transport: 'stdio',
  command: '',
  args: [],
  env: {},
  disabled: false,
  autoApprove: [],
}

export function MCPConfigPanel() {
  const [config, setConfig] = useState<{ mcpServers: Record<string, MCPServerConfig> }>({ mcpServers: {} })
  const [status, setStatus] = useState<MCPStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [reloading, setReloading] = useState(false)
  const [editingName, setEditingName] = useState<string | null>(null)
  const [editingTemplate, setEditingTemplate] = useState<MCPTemplate | null>(null)
  const [showTemplates, setShowTemplates] = useState(false)
  const [expandedServers, setExpandedServers] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [savedFlash, setSavedFlash] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [saving, setSaving] = useState(false)
  const busy = useRef(false)
  const { confirm, ConfirmDialog } = useConfirm()

  // 拉取当前配置 + 状态
  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [cfgRes, stRes] = await Promise.all([
        apiRequest<{mcpServers: Record<string, MCPServerConfig>}>('/ai-assistant/mcp/config'),
        apiRequest<MCPStatus>('/ai-assistant/mcp/status'),
      ])
      if (!cfgRes.success) throw new Error(cfgRes.error)
      if (!stRes.success) throw new Error(stRes.error)
      const cfg = cfgRes.data, st = stRes.data
      if (!validConfig(cfg) || !validStatus(st)) {
        throw new Error('MCP 配置或状态响应格式错误')
      }
      setConfig(cfg)
      setStatus(st)
      setLoaded(true)
    } catch (e: any) {
      setError(e?.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  // 保存配置
  const saveConfig = async (next: { mcpServers: Record<string, MCPServerConfig> }) => {
    if (busy.current || !loaded) return false
    busy.current = true
    setSaving(true)
    setSavedFlash(false)
    try {
      const result = await apiRequest('/ai-assistant/mcp/config', {
        method: 'PUT', body: JSON.stringify({config:next}),
      })
      if (!result.success) throw new Error(result.error)
      if (result.data?.success !== true || result.data?.saved !== true) throw new Error('服务未确认配置已保存')
      setConfig(next)
      setSavedFlash(true)
      setTimeout(() => setSavedFlash(false), 1500)
      setError(null)
      return true
    } catch (e: any) {
      setError(`保存失败：${e?.message || e}`)
      return false
    } finally {
      busy.current = false
      setSaving(false)
    }
  }

  const reload = async () => {
    if (busy.current) return
    busy.current = true
    setReloading(true)
    setError(null)
    try {
      const result = await apiRequest('/ai-assistant/mcp/reload', {method:'POST'})
      if (!result.success) throw new Error(result.error)
      await refresh()
    } catch (e: any) {
      setError(`重连失败：${e?.message || e}`)
    } finally {
      busy.current = false
      setReloading(false)
    }
  }

  const upsertServer = async (name: string, server: MCPServerConfig, oldName?: string) => {
    name = name.trim()
    if (!name || (name !== oldName && Object.hasOwn(config.mcpServers,name))) {
      setError(name ? '服务器名称已存在' : '服务器名称不能为空')
      return
    }
    const next = { ...config, mcpServers: {...config.mcpServers} }
    if (oldName && oldName !== name) delete next.mcpServers[oldName]
    next.mcpServers[name] = server
    if (await saveConfig(next)) setEditingName(null)
  }

  const deleteServer = async (name: string) => {
    if (busy.current) return
    const ok = await confirm(`确认删除 MCP 服务器 "${name}"？`, { type: 'warning', title: '删除 MCP 服务器', confirmText: '删除', cancelText: '取消' })
    if (!ok) return
    const next = { ...config, mcpServers: {...config.mcpServers} }
    delete next.mcpServers[name]
    if (await saveConfig(next)) await reload()
  }

  const toggleDisabled = async (name: string) => {
    const next = { ...config, mcpServers: {...config.mcpServers,
      [name]: {...config.mcpServers[name], disabled: !config.mcpServers[name].disabled},
    } }
    await saveConfig(next)
  }

  const toggleExpanded = (name: string) => {
    const next = new Set(expandedServers)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    setExpandedServers(next)
  }

  const serverNames = Object.keys(config.mcpServers)

  return (
    <div className="space-y-4">
      {/* 顶部说明 */}
      <div className="p-3 rounded-md bg-violet-50 border border-violet-200/50 text-xs text-violet-800 leading-relaxed">
        <div className="flex items-start gap-2">
          <Server className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>
            <strong>MCP（Model Context Protocol）</strong> 让你接入第三方工具到 AutoFlow 小助手。
            支持 <code className="px-1 bg-violet-100 rounded">stdio</code>（本地命令）、
            <code className="px-1 bg-violet-100 rounded mx-0.5">sse</code> 和
            <code className="px-1 bg-violet-100 rounded ml-0.5">http</code>（远程服务）。
            配置格式与 Claude Desktop 兼容。
            <a
              className="ml-2 text-violet-700 underline inline-flex items-center gap-0.5"
              href="https://github.com/modelcontextprotocol/servers"
              target="_blank"
              rel="noreferrer"
              onClick={(e) => {
                e.preventDefault()
                window.open('https://github.com/modelcontextprotocol/servers', '_blank')
              }}
            >
              官方 server 列表 <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </div>

      {/* 统计 + 操作 */}
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs text-gray-600">
          {loading ? '加载中…' : (
            <>
              共 <strong>{serverNames.length}</strong> 个服务器
              {status && (
                <>
                  {' · '}已连接 <strong className="text-green-600">{status.servers.filter(s => s.connected).length}</strong>
                  {' · '}注入 <strong className="text-violet-600">{status.total_tools_injected}</strong> 个工具
                </>
              )}
              {savedFlash && <span className="ml-2 text-green-600 inline-flex items-center gap-0.5"><CheckCircle2 className="w-3 h-3" /> 已保存</span>}
            </>
          )}
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setShowTemplates(true)} disabled={loading || saving || reloading || !loaded}>
            <Sparkles className="w-3.5 h-3.5" />
            <span className="ml-1">推荐模板</span>
          </Button>
          <Button size="sm" variant="outline" onClick={reload} disabled={reloading || loading || saving || !loaded}>
            {reloading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            <span className="ml-1">重新连接</span>
          </Button>
          <Button size="sm" onClick={() => { setEditingTemplate(null); setEditingName('__new__') }} disabled={loading || saving || reloading || !loaded}>
            <Plus className="w-3.5 h-3.5" />
            <span className="ml-1">添加</span>
          </Button>
        </div>
      </div>

      {error && editingName === null && (
        <div className="p-2.5 rounded-md bg-red-50 border border-red-200 text-xs text-red-700 flex items-start gap-1.5">
          <AlertCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          <span role="alert">{error}</span><button disabled={loading || saving || reloading} onClick={refresh}>重新读取配置</button>
        </div>
      )}

      {/* 服务器列表 */}
      <div className="space-y-2">
        {serverNames.length === 0 && !loading && loaded && (
          <div className="text-center py-8 text-sm text-gray-500">
            还没有配置 MCP 服务器，点上方"添加"开始
          </div>
        )}
        {serverNames.map((name) => {
          const server = config.mcpServers[name]
          const st = status?.servers.find((s) => s.name === name)
          const isExpanded = expandedServers.has(name)
          return (
            <div
              key={name}
              className={`border rounded-md ${server.disabled ? 'border-gray-200 bg-gray-50/50' : (st?.connected ? 'border-green-200 bg-green-50/30' : 'border-amber-200 bg-amber-50/30')}`}
            >
              <div className="px-3 py-2.5 flex items-center gap-2">
                <button
                  onClick={() => toggleExpanded(name)}
                  className="text-gray-500 hover:text-gray-800 p-0.5"
                >
                  {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                </button>
                {server.disabled ? (
                  <XCircle className="w-4 h-4 text-gray-400" />
                ) : st?.connected ? (
                  <CheckCircle2 className="w-4 h-4 text-green-600" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-amber-600" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-gray-900 truncate">{name}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 uppercase">
                      {server.transport || 'stdio'}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 truncate mt-0.5">
                    {server.disabled
                      ? '已禁用'
                      : st?.connected
                        ? `已连接 · ${st.tool_count} 个工具`
                        : st?.last_error
                          ? `连接失败：${st.last_error.slice(0, 60)}`
                          : '未连接'}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    disabled={saving || reloading || loading}
                    onClick={() => toggleDisabled(name)}
                    className="text-xs px-2 py-1 rounded border border-gray-200 hover:bg-gray-100 text-gray-700"
                  >
                    {server.disabled ? '启用' : '禁用'}
                  </button>
                  <button
                    disabled={saving || reloading || loading}
                    onClick={() => setEditingName(name)}
                    className="text-xs px-2 py-1 rounded border border-blue-200 text-blue-700 hover:bg-blue-50"
                  >
                    编辑
                  </button>
                  <button
                    disabled={saving || reloading || loading}
                    aria-label={`删除 MCP 服务器 ${name}`}
                    onClick={() => deleteServer(name)}
                    className="text-xs p-1 rounded border border-red-200 text-red-600 hover:bg-red-50"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
              {isExpanded && st && (
                <div className="px-3 pb-3 pt-1 border-t border-gray-100/80 text-xs space-y-2">
                  {st.tools.length > 0 ? (
                    <div>
                      <div className="text-gray-600 mb-1">暴露的工具（{st.tools.length}）：</div>
                      <div className="space-y-1 max-h-48 overflow-y-auto">
                        {st.tools.map((t) => (
                          <div key={t.name} className="flex items-baseline gap-2">
                            <code className="text-violet-700 font-mono text-[11px]">{t.name}</code>
                            <span className="text-gray-500 text-[11px]">{t.description}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="text-gray-500">{st.connected ? '此服务器没有暴露工具' : '未连接'}</div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* 编辑/新增表单 */}
      {editingName !== null && (
        <ServerEditModal
          name={editingName === '__new__' ? (editingTemplate?.name || '') : editingName}
          server={
            editingName === '__new__'
              ? (editingTemplate ? templateToServerConfig(editingTemplate) : DEFAULT_NEW_SERVER)
              : config.mcpServers[editingName]
          }
          template={editingName === '__new__' ? editingTemplate : null}
          existingNames={serverNames}
          isNew={editingName === '__new__'}
          saving={saving}
          error={error}
          onClose={() => { if (!busy.current) { setEditingName(null); setEditingTemplate(null); setError(null) } }}
          onSave={(name, server) => upsertServer(name, server, editingName === '__new__' ? undefined : editingName)}
        />
      )}

      {/* 推荐模板选择器 */}
      {showTemplates && (
        <TemplatePicker
          existingNames={serverNames}
          onClose={() => setShowTemplates(false)}
          onPick={(tpl) => {
            setShowTemplates(false)
            setEditingTemplate(tpl)
            setEditingName('__new__')
          }}
        />
      )}
      <ConfirmDialog />
    </div>
  )
}

// =============================================================================
// 模板 → MCPServerConfig 转换
// =============================================================================
function templateToServerConfig(tpl: MCPTemplate): MCPServerConfig {
  return {
    transport: tpl.transport,
    command: tpl.command,
    args: tpl.args ? [...tpl.args] : undefined,
    env: tpl.env ? { ...tpl.env } : undefined,
    url: tpl.url,
    headers: tpl.headers ? { ...tpl.headers } : undefined,
    autoApprove: tpl.autoApprove ? [...tpl.autoApprove] : undefined,
    disabled: false,
  }
}

// =============================================================================
// 编辑/新增 Server 表单
// =============================================================================

interface ServerEditModalProps {
  isNew: boolean
  saving: boolean
  error: string | null
  name: string
  server: MCPServerConfig
  template?: MCPTemplate | null
  existingNames: string[]
  onClose: () => void
  onSave: (name: string, server: MCPServerConfig) => void | Promise<void>
}

function ServerEditModal({ name: initialName, server: initialServer, template, existingNames, isNew, saving, error, onClose, onSave }: ServerEditModalProps) {
  const [name, setName] = useState(initialName)
  const [transport, setTransport] = useState<'stdio' | 'sse' | 'http'>(initialServer.transport || 'stdio')
  const [command, setCommand] = useState(initialServer.command || '')
  const [args, setArgs] = useState((initialServer.args || []).join('\n'))
  const [envText, setEnvText] = useState(
    Object.entries(initialServer.env || {}).map(([k, v]) => `${k}=${v}`).join('\n')
  )
  const [cwd, setCwd] = useState(initialServer.cwd || '')
  const [url, setUrl] = useState(initialServer.url || '')
  const [headersText, setHeadersText] = useState(
    Object.entries(initialServer.headers || {}).map(([k, v]) => `${k}: ${v}`).join('\n')
  )
  const [autoApproveText, setAutoApproveText] = useState(
    (initialServer.autoApprove || []).join('\n')
  )

  const nameConflict = isNew && existingNames.includes(name.trim())

  const handleSave = () => {
    if (saving || !name.trim()) return
    if (nameConflict) return

    const envLines = envText.split('\n').map(l => l.trim()).filter(Boolean)
    const env: Record<string, string> = {}
    for (const line of envLines) {
      const idx = line.indexOf('=')
      if (idx > 0) env[line.slice(0, idx).trim()] = line.slice(idx + 1).trim()
    }

    const headersLines = headersText.split('\n').map(l => l.trim()).filter(Boolean)
    const headers: Record<string, string> = {}
    for (const line of headersLines) {
      const idx = line.indexOf(':')
      if (idx > 0) headers[line.slice(0, idx).trim()] = line.slice(idx + 1).trim()
    }

    const autoApprove = autoApproveText.split('\n').map(l => l.trim()).filter(Boolean)
    const argsList = args.split('\n').map(l => l.trim()).filter(Boolean)

    const server: MCPServerConfig = {
      transport,
      ...(transport === 'stdio' ? {
        command: command.trim(),
        args: argsList,
        env,
        ...(cwd.trim() ? { cwd: cwd.trim() } : {}),
      } : {
        url: url.trim(),
        ...(Object.keys(headers).length > 0 ? { headers } : {}),
      }),
      disabled: initialServer.disabled || false,
      ...(autoApprove.length > 0 ? { autoApprove } : {}),
    }
    onSave(name.trim(), server)
  }

  return (
    <div
      className="fixed inset-0 z-[10001] bg-black/40 backdrop-blur-sm flex items-center justify-center px-4 py-14"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl w-full max-w-2xl flex flex-col overflow-hidden"
        style={{ maxHeight: 'min(calc(100vh - 7rem), 620px)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header（固定不滚动） */}
        <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
          <h3 className="font-semibold text-gray-800">
            {isNew ? '添加 MCP 服务器' : `编辑：${initialName}`}
          </h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800 text-lg leading-none">×</button>
        </div>

        {/* Body（中间区域滚动） */}
        <fieldset disabled={saving} className="px-5 py-4 space-y-3 overflow-y-auto flex-1">
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
          {/* 模板来源提示 */}
          {template && (
            <div className="p-2.5 rounded-md bg-violet-50 border border-violet-200/60 text-xs text-violet-800">
              <div className="flex items-center gap-1.5 font-semibold mb-1">
                <Sparkles className="w-3.5 h-3.5" />
                正在使用模板：{template.icon} {template.title}
              </div>
              <div className="text-violet-700/90 mb-1">{template.description}</div>
              {template.needsConfig.length > 0 && (
                <div className="text-violet-700 mt-1.5 pt-1.5 border-t border-violet-200/60">
                  <div className="font-semibold mb-0.5">需要你填的字段：</div>
                  <ul className="list-disc list-inside space-y-0.5">
                    {template.needsConfig.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                  <div className="mt-1 text-violet-700/70">
                    把下面字段中尖括号占位（&lt;...&gt;）替换为你的实际值即可。
                  </div>
                </div>
              )}
            </div>
          )}

          <div>
            <Label className="text-gray-700 text-xs">服务器名称（唯一标识，不能含空格）</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value.replace(/\s/g, '-'))}
              placeholder="例如 filesystem / weather / github"
              disabled={!isNew}
              className="bg-white text-black border-gray-300 mt-1 h-8 text-sm"
            />
            {nameConflict && <p className="text-xs text-red-600 mt-1">名称已存在</p>}
          </div>
          <div>
            <Label className="text-gray-700 text-xs">传输方式</Label>
            <div className="flex gap-2 mt-1">
              {(['stdio', 'sse', 'http'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTransport(t)}
                  className={`px-3 py-1 text-xs rounded-md border ${transport === t ? 'border-violet-500 bg-violet-50 text-violet-700 font-medium' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}
                >
                  {t}
                </button>
              ))}
            </div>
            <p className="text-[11px] text-gray-500 mt-1">
              {transport === 'stdio' && '本地子进程（npx / node / python 等启动 MCP server）'}
              {transport === 'sse' && '远程 SSE 流（Server-Sent Events）'}
              {transport === 'http' && '远程 HTTP（Streamable HTTP）'}
            </p>
          </div>

          {transport === 'stdio' ? (
            <>
              <div>
                <Label className="text-gray-700 text-xs">启动命令 *</Label>
                <Input
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                  placeholder="例如 npx / node / python"
                  className="bg-white text-black border-gray-300 mt-1 h-8 font-mono text-sm"
                />
              </div>
              <div>
                <Label className="text-gray-700 text-xs">命令参数（每行一个）</Label>
                <textarea
                  value={args}
                  onChange={(e) => setArgs(e.target.value)}
                  placeholder={'-y\n@modelcontextprotocol/server-filesystem\nD:\\Documents'}
                  rows={3}
                  className="w-full px-3 py-1.5 text-xs rounded-md border border-gray-300 bg-white text-black mt-1 font-mono"
                />
              </div>
              <div>
                <Label className="text-gray-700 text-xs">环境变量（KEY=VALUE，每行一个）</Label>
                <textarea
                  value={envText}
                  onChange={(e) => setEnvText(e.target.value)}
                  placeholder={'API_KEY=xxx\nDEBUG=1'}
                  rows={2}
                  className="w-full px-3 py-1.5 text-xs rounded-md border border-gray-300 bg-white text-black mt-1 font-mono"
                />
              </div>
              <div>
                <Label className="text-gray-700 text-xs">工作目录（可选）</Label>
                <Input
                  value={cwd}
                  onChange={(e) => setCwd(e.target.value)}
                  placeholder="留空使用 backend 当前目录"
                  className="bg-white text-black border-gray-300 mt-1 h-8 text-sm"
                />
              </div>
            </>
          ) : (
            <>
              <div>
                <Label className="text-gray-700 text-xs">服务器 URL *</Label>
                <Input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder={transport === 'sse' ? 'https://example.com/sse' : 'https://example.com/mcp'}
                  className="bg-white text-black border-gray-300 mt-1 h-8 font-mono text-sm"
                />
              </div>
              <div>
                <Label className="text-gray-700 text-xs">请求头（Key: Value，每行一个）</Label>
                <textarea
                  value={headersText}
                  onChange={(e) => setHeadersText(e.target.value)}
                  placeholder={'Authorization: Bearer xxx\nX-API-Key: yyy'}
                  rows={2}
                  className="w-full px-3 py-1.5 text-xs rounded-md border border-gray-300 bg-white text-black mt-1 font-mono"
                />
              </div>
            </>
          )}

          <div>
            <Label className="text-gray-700 text-xs">自动批准的工具（可选，每行一个工具名）</Label>
            <textarea
              value={autoApproveText}
              onChange={(e) => setAutoApproveText(e.target.value)}
              placeholder={'read_file\nlist_directory'}
              rows={2}
              className="w-full px-3 py-1.5 text-xs rounded-md border border-gray-300 bg-white text-black mt-1 font-mono"
            />
            <p className="text-[11px] text-gray-500 mt-1">
              这些工具调用时不会要求确认。其他工具默认需要确认。
            </p>
          </div>
        </fieldset>

        {/* Footer（固定不滚动） */}
        <div className="px-5 py-3 border-t border-gray-200 flex justify-end gap-2 flex-shrink-0 bg-white">
          <Button variant="outline" onClick={onClose} disabled={saving}>取消</Button>
          <Button onClick={handleSave} disabled={saving || !name.trim() || nameConflict || (transport === 'stdio' ? !command.trim() : !url.trim())}>
            保存
          </Button>
        </div>
      </div>
    </div>
  )
}


// =============================================================================
// 推荐模板选择器
// =============================================================================
interface TemplatePickerProps {
  existingNames: string[]
  onClose: () => void
  onPick: (tpl: MCPTemplate) => void
}

function TemplatePicker({ existingNames, onClose, onPick }: TemplatePickerProps) {
  const [query, setQuery] = useState('')

  const grouped = MCP_TEMPLATES.reduce<Record<string, MCPTemplate[]>>((acc, tpl) => {
    if (query) {
      const q = query.toLowerCase()
      const hit =
        tpl.title.toLowerCase().includes(q) ||
        tpl.description.toLowerCase().includes(q) ||
        tpl.id.toLowerCase().includes(q)
      if (!hit) return acc
    }
    ;(acc[tpl.category] ||= []).push(tpl)
    return acc
  }, {})

  return (
    <div
      className="fixed inset-0 z-[10001] bg-black/40 backdrop-blur-sm flex items-center justify-center px-4 py-14"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl w-full max-w-3xl flex flex-col overflow-hidden"
        style={{ maxHeight: 'min(calc(100vh - 7rem), 580px)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-4 py-2 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <Sparkles className="w-4 h-4 text-violet-600 flex-shrink-0" />
            <h3 className="font-semibold text-gray-800 text-sm">推荐 MCP 模板</h3>
            <span className="text-[11px] text-gray-500 truncate">选一个一键预填表单（保存前可改）</span>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800 text-lg leading-none flex-shrink-0">×</button>
        </div>

        {/* 搜索 */}
        <div className="px-4 py-2 border-b border-gray-100 flex-shrink-0">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索模板名称或描述…"
              className="w-full pl-8 pr-3 py-1.5 text-sm rounded-md border border-gray-300 bg-white text-black focus:outline-none focus:border-violet-500"
            />
          </div>
        </div>

        {/* 列表 */}
        <div className="px-4 py-2.5 overflow-y-auto flex-1 space-y-3">
          {Object.keys(grouped).length === 0 && (
            <div className="text-center text-sm text-gray-500 py-8">没有找到匹配的模板</div>
          )}
          {Object.entries(grouped).map(([cat, list]) => (
            <div key={cat}>
              <div className="text-[10.5px] font-semibold text-gray-500 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                <span>{TEMPLATE_CATEGORIES[cat] || cat}</span>
                <span className="text-gray-400 font-normal normal-case">· {list.length}</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
                {list.map((tpl) => {
                  const exists = existingNames.includes(tpl.name)
                  return (
                    <button
                      key={tpl.id}
                      type="button"
                      disabled={exists}
                      onClick={() => onPick(tpl)}
                      className={`text-left p-2 rounded-md border transition-all ${
                        exists
                          ? 'border-gray-200 bg-gray-50 opacity-60 cursor-not-allowed'
                          : 'border-gray-200 bg-white hover:border-violet-400 hover:bg-violet-50/40 hover:shadow-sm cursor-pointer'
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <span className="text-base leading-none mt-0.5">{tpl.icon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1 mb-0.5 flex-wrap">
                            <span className="font-medium text-[13px] text-gray-900 truncate">{tpl.title}</span>
                            {tpl.recommended && (
                              <span className="text-[9px] font-bold tracking-wider px-1 py-px rounded bg-violet-100 text-violet-700 leading-none flex items-center gap-0.5">
                                <Star className="w-2.5 h-2.5 fill-current" />
                                推荐
                              </span>
                            )}
                            {exists && (
                              <span className="text-[10px] text-gray-500 px-1.5 py-px rounded bg-gray-100">已添加</span>
                            )}
                          </div>
                          <div className="text-[11px] text-gray-600 leading-snug line-clamp-2">{tpl.description}</div>
                          {tpl.needsConfig.length > 0 && (
                            <div className="mt-0.5 text-[10px] text-amber-700 truncate">
                              需配置：{tpl.needsConfig[0]}
                              {tpl.needsConfig.length > 1 && ' 等'}
                            </div>
                          )}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-gray-200 flex justify-between items-center flex-shrink-0 bg-gray-50/50">
          <a
            href="https://github.com/modelcontextprotocol/servers"
            target="_blank"
            rel="noreferrer"
            onClick={(e) => {
              e.preventDefault()
              window.open('https://github.com/modelcontextprotocol/servers', '_blank')
            }}
            className="text-xs text-violet-700 hover:text-violet-900 inline-flex items-center gap-0.5"
          >
            浏览更多 MCP 服务器 <ExternalLink className="w-3 h-3" />
          </a>
          <Button variant="outline" size="sm" onClick={onClose}>关闭</Button>
        </div>
      </div>
    </div>
  )
}
