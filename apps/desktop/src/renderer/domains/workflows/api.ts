// Source: WebRPA@5ccb900e, services/api.ts; see SOURCE.md for license and adaptation boundaries.
import { studioFetch } from './api/transport'
import { getBackendBaseUrl } from './api/config'

// 获取后端 API 基础地址
function getApiBase(): string {
  return `${getBackendBaseUrl()}/api`
}

let API_BASE = getApiBase()

// 配置变化后刷新 API_BASE，确保后续请求使用最新地址
export function updateApiBase() {
  API_BASE = getApiBase()
}

// 获取当前 API 基础地址
export function getApiBaseUrl(): string {
  return API_BASE
}

// 获取后端服务 URL（不含 /api 前缀）
export function getBackendUrl(): string {
  return getBackendBaseUrl()
}

// 远程访问令牌：本机访问后端会免验（忽略此头），仅当从其它设备访问 WebRPA 时才需要在「安全设置」里填入
export function getAuthToken(): string { return '' }
export function setAuthToken(_token: string): void { /* AutoFlow owns authentication. */ }

export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: string
}

// 调用 API 请求
export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  try {
    // 确保配置已加载
    const { preloadConfig } = await import('./api/config')
    await preloadConfig()
    
    const url = `${API_BASE}${endpoint}`
    const isFormData = options.body instanceof FormData
    const _authToken = getAuthToken()
    const _authHeader: Record<string, string> = _authToken ? { 'X-WebRPA-Token': _authToken } : {}
    const response = await studioFetch(url, {
      ...options,
      headers: isFormData
        ? { ..._authHeader, ...(options.headers as Record<string, string>) }
        : { 'Content-Type': 'application/json', ..._authHeader, ...(options.headers as Record<string, string>) },
    })
    if (!response.ok) {
      // 尝试解析后端返回的详细错误信息（FastAPI 422 的 detail 字段）
      let detailMessage = ''
      try {
        const errBody = await response.json()
        if (errBody) {
          if (typeof errBody.detail === 'string') {
            detailMessage = errBody.detail
          } else if (Array.isArray(errBody.detail)) {
            detailMessage = errBody.detail
              .map((e: any) => {
                const loc = Array.isArray(e?.loc) ? e.loc.join('.') : ''
                return `${loc ? loc + ': ' : ''}${e?.msg || JSON.stringify(e)}`
              })
              .join('; ')
          } else if (typeof errBody.message === 'string') {
            detailMessage = errBody.message
          } else if (typeof errBody.error === 'string') {
            detailMessage = errBody.error
          }
        }
      } catch {
        // 忽略 JSON 解析失败
      }
      const baseError = `HTTP ${response.status}: ${response.statusText}`
      return { success: false, error: detailMessage ? `${baseError} - ${detailMessage}` : baseError }
    }
    const data = await response.json()
    return { success: true, data }
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : '请求失败' }
  }
}

// ==================== 系统 API ====================
export const systemApi = {
  getConfig: () => apiRequest('/system/config'),
  // 浏览器配置同步（供计划任务/触发器等后端自治执行读取用户选择的浏览器）
  getBrowserConfig: () => apiRequest<{ success: boolean; config: Record<string, unknown> }>('/system/browser-config'),
  setBrowserConfig: (cfg: Record<string, unknown>) =>
    apiRequest<{ success: boolean; config: Record<string, unknown> }>('/system/browser-config', {
      method: 'POST',
      body: JSON.stringify(cfg),
    }),
  selectFolder: (title?: string, initialDir?: string) =>
    apiRequest('/system/select-folder', { 
      method: 'POST', 
      body: JSON.stringify({ title, initialDir }) 
    }),
  selectFile: (title?: string, initialDir?: string, fileTypes?: Array<[string, string]>) =>
    apiRequest('/system/select-file', { 
      method: 'POST', 
      body: JSON.stringify({ title, initialDir, fileTypes }) 
    }),
  openUrl: (url: string) =>
    apiRequest('/system/open-url', { method: 'POST', body: JSON.stringify({ url }) }),
  setCustomHotkeys: (shortcuts: Record<string, string>) =>
    apiRequest('/system/custom-hotkeys', { method: 'POST', body: JSON.stringify({ shortcuts }) }),
  getMousePosition: () => apiRequest('/system/mouse-position'),
  /** 写入系统剪贴板（焦点无关，供元素选择器自动复制选择器使用） */
  setClipboard: (text: string) =>
    apiRequest('/system/set-clipboard', { method: 'POST', body: JSON.stringify({ text }) }),
  takeScreenshot: (params?: any) =>
    apiRequest('/system/screenshot', { method: 'POST', body: JSON.stringify(params || {}) }),
  screenshotBase64: () =>
    apiRequest<{ success: boolean; dataUrl?: string; width?: number; height?: number; error?: string }>(
      '/system/screenshot-base64', { method: 'POST', body: '{}' }
    ),
}

// ==================== 工作流 API ====================
export const workflowApi = {
  list: () => apiRequest('/workflows'),
  get: (id: string) => apiRequest(`/workflows/${id}`),
  create: (data: any) =>
    apiRequest('/workflows', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: any) =>
    apiRequest(`/workflows/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) =>
    apiRequest(`/workflows/${id}`, { method: 'DELETE' }),
  execute: (id: string, params?: any) =>
    apiRequest(`/workflows/${id}/execute`, { method: 'POST', body: JSON.stringify(params || {}) }),
  stop: (id: string) =>
    apiRequest(`/workflows/${id}/stop`, { method: 'POST' }),
  /** 调试：从暂停处继续 */
  debugResume: (id: string) =>
    apiRequest(`/workflows/${id}/debug/resume`, { method: 'POST' }),
  /** 调试：单步执行 */
  debugStep: (id: string) =>
    apiRequest(`/workflows/${id}/debug/step`, { method: 'POST' }),
  /** 调试：运行中更新断点 */
  debugBreakpoints: (id: string, breakpoints: string[]) =>
    apiRequest(`/workflows/${id}/debug/breakpoints`, { method: 'POST', body: JSON.stringify({ breakpoints }) }),
  /** 获取本次执行收集到的完整数据（不限 20 条预览上限） */
  getFullData: (id: string) =>
    apiRequest<{ rows: Record<string, unknown>[]; columns: string[]; total: number }>(
      `/workflows/${id}/data/full`
    ),
  /** 取最近一次执行收集到的完整数据（兜底：currentExecutionWorkflowId 丢失或不一致时用） */
  getLatestFullData: () =>
    apiRequest<{ workflow_id: string; rows: Record<string, unknown>[]; columns: string[]; total: number }>(
      `/workflows/data-latest/full`
    ),
  /** 导出工作流为脚本（target: 'selenium' | 'playwright-js'） */
  exportScript: (id: string, target: string) =>
    apiRequest<{ code: string; filename: string; target: string }>(
      `/workflows/${id}/export-script?target=${encodeURIComponent(target)}`
    ),
  /** 取后端执行期间产生/更新的变量（计划任务等后端自治执行的结果，进程内有效） */
  getGlobalVariables: () =>
    apiRequest<{ variables: Record<string, unknown>; count: number }>(
      '/workflows/global-variables'
    ),
}

// ==================== 本地工作流 API ====================
export const localWorkflowApi = {
  list: (folder?: string) => 
    apiRequest('/local-workflows/list', { 
      method: 'POST', 
      body: JSON.stringify({ folder }) 
    }),
  /** 读取单个本地工作流内容。
   *  注意后端真实路由是 /local-workflows/load/{filename:path}（历史上这里误写成
   *  /local-workflows/{id}，该路径没有对应路由、请求恒 404，导致监控页加载工作流、
   *  AI 技能读取本地工作流等功能全部静默失效）。
   *  该端点在未传 folder 时会用「活动工作流文件夹」兜底，并自动兼容 WebDAV。 */
  get: (filename: string) =>
    apiRequest(`/local-workflows/load/${encodeURIComponent(filename)}`),
  save: (data: any) =>
    apiRequest('/local-workflows/save-to-folder', { method: 'POST', body: JSON.stringify(data) }),
  delete: (id: string) =>
    apiRequest(`/local-workflows/${id}`, { method: 'DELETE' }),
  import: (data: any) =>
    apiRequest('/local-workflows/import', { method: 'POST', body: JSON.stringify(data) }),
  export: (id: string) => apiRequest(`/local-workflows/${id}/export`),
  getDefaultFolder: () => apiRequest('/local-workflows/default-folder'),

  // 活动工作流文件夹（服务端持久化，供计划任务/触发器等后端自治操作解析用户自定义路径）
  getActiveFolder: () => apiRequest<{ folder: string; default: string }>('/local-workflows/active-folder'),
  setActiveFolder: (folder: string) =>
    apiRequest<{ success: boolean; folder: string }>('/local-workflows/active-folder', {
      method: 'POST',
      body: JSON.stringify({ folder }),
    }),
  // 自愈固化（健康基线）开关
  getSelfHeal: (filename: string, folder?: string) =>
    apiRequest<{ success: boolean; enabled: boolean; selfHeal?: any; error?: string }>(
      `/local-workflows/self-heal/${encodeURIComponent(filename)}${folder ? `?folder=${encodeURIComponent(folder)}` : ''}`
    ),
  setSelfHeal: (filename: string, enabled: boolean, folder?: string) =>
    apiRequest<{ success: boolean; enabled: boolean; error?: string }>(
      '/local-workflows/self-heal', { method: 'POST', body: JSON.stringify({ filename, enabled, folder }) }
    ),
}

// ==================== 执行器 API ====================
export const executorApi = {
  execute: (data: any) =>
    apiRequest('/executor/execute', { method: 'POST', body: JSON.stringify(data) }),
  getTypes: () => apiRequest('/executor/types'),
}

// ==================== 图像资源 API ====================
export const imageAssetApi = {
  list: () => apiRequest('/image-assets'),
  listFolders: () => apiRequest('/image-assets/folders'),
  get: (id: string) => apiRequest(`/image-assets/${id}`),
  upload: (file: File, folder?: string) => {
      const formData = new FormData()
      formData.append('file', file)
    if (folder) formData.append('folder', folder)
    return apiRequest('/image-assets/upload', { method: 'POST', body: formData })
  },
  delete: (id: string) => apiRequest(`/image-assets/${id}`, { method: 'DELETE' }),
  createFolder: (name: string, parentPath?: string) =>
    apiRequest('/image-assets/folders', { method: 'POST', body: JSON.stringify({ name, parentPath }) }),
  renameFolder: (oldPath: string, newName: string) =>
    apiRequest('/image-assets/folders/rename', { method: 'PUT', body: JSON.stringify({ oldPath, newName }) }),
  deleteFolder: (folderPath: string) =>
    apiRequest('/image-assets/folders', { method: 'DELETE', body: JSON.stringify({ folderPath }) }),
  rename: (assetId: string, newName: string) =>
    apiRequest(`/image-assets/${assetId}/rename?newName=${encodeURIComponent(newName)}`, { method: 'PUT' }),
  moveAsset: (assetId: string, targetFolder?: string) =>
    apiRequest('/image-assets/move', { method: 'PUT', body: JSON.stringify({ assetId, targetFolder }) }),
}

// ==================== 定时任务 API ====================
export const scheduledTaskApi = {
  list: () => apiRequest('/scheduled-tasks/list'),
  get: (id: string) => apiRequest(`/scheduled-tasks/${id}`),
  create: (data: any) =>
    apiRequest('/scheduled-tasks', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: any) =>
    apiRequest(`/scheduled-tasks/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) =>
    apiRequest(`/scheduled-tasks/${id}`, { method: 'DELETE' }),
  toggle: (id: string, enabled: boolean) =>
    apiRequest(`/scheduled-tasks/${id}/toggle`, { method: 'POST', body: JSON.stringify({ enabled }) }),
  execute: (id: string) =>
    apiRequest(`/scheduled-tasks/${id}/execute`, { method: 'POST' }),
  stop: (id: string) =>
    apiRequest(`/scheduled-tasks/${id}/stop`, { method: 'POST' }),
  getTaskLogs: (id: string, limit: number = 100) => 
    apiRequest(`/scheduled-tasks/${id}/logs?limit=${limit}`),
  getAllLogs: (limit: number = 100) => 
    apiRequest(`/scheduled-tasks/logs/all?limit=${limit}`),
  clearTaskLogs: (id: string) =>
    apiRequest(`/scheduled-tasks/${id}/logs`, { method: 'DELETE' }),
  clearAllLogs: () =>
    apiRequest('/scheduled-tasks/logs/all', { method: 'DELETE' }),
  getStatistics: () => 
    apiRequest('/scheduled-tasks/statistics/summary'),
}

// ==================== 自动化浏览器 API ====================
export const browserApi = {
  getStatus: () => apiRequest('/browser/status'),
  /** 检测 Playwright 内置 Chromium 是否可用（浏览器扩展兜底是否生效） */
  chromiumStatus: () => apiRequest('/browser/chromium-status'),
  open: (url?: string, browserConfig?: any) =>
    apiRequest('/browser/open', { method: 'POST', body: JSON.stringify({ url, browserConfig }) }),
  launch: (url?: string) =>
    apiRequest('/browser/launch', { method: 'POST', body: JSON.stringify({ url }) }),
  close: () => apiRequest('/browser/close', { method: 'POST' }),
  navigate: (url: string) =>
    apiRequest('/browser/navigate', { method: 'POST', body: JSON.stringify({ url }) }),
  getUrl: () => apiRequest('/browser/url'),
  getSelector: (description: string) =>
    apiRequest('/browser/get-selector', { method: 'POST', body: JSON.stringify({ description }) }),
  startPicker: () => apiRequest('/element-picker/start', { method: 'POST', body: JSON.stringify({}) }),
  stopPicker: () => apiRequest('/element-picker/stop', { method: 'POST' }),
}

// ==================== 元素选择器 API ====================
export const elementPickerApi = {
  /**
   * 启动元素选择器
   * @param url 可选，要打开的目标页面 URL
   * @param browserConfig 可选，浏览器配置
   */
  start: (url?: string, browserConfig?: any) =>
    apiRequest('/element-picker/start', {
      method: 'POST',
      body: JSON.stringify({ url: url || null, browserConfig: browserConfig || null }),
    }),
  stop: () => apiRequest('/element-picker/stop', { method: 'POST' }),
  getResult: () => apiRequest('/element-picker/result'),
  getSelected: () => apiRequest('/element-picker/selected'),
  getSimilar: () => apiRequest('/element-picker/similar'),
  getStatus: () => apiRequest('/element-picker/status'),
  /** 在当前浏览器页面上测试选择器是否命中并高亮匹配项 */
  testSelector: (selector: string, hints?: Record<string, unknown>, highlight = true) =>
    apiRequest<{
      success: boolean
      matched?: boolean
      count?: number
      matchedSelector?: string
      isPrimary?: boolean
      element?: { tag?: string; text?: string }
      error?: string
    }>('/element-picker/test-selector', {
      method: 'POST',
      body: JSON.stringify({ selector, hints: hints || null, highlight }),
    }),
}

// ==================== 网页智能录制器 API ====================
export const recorderApi = {
  start: (sessionId?: string) => apiRequest('/recorder/start', { method: 'POST', body: JSON.stringify({ sessionId }) }),
  stop: (sessionId?: string, afterSeq = 0) => apiRequest('/recorder/stop', { method: 'POST', body: JSON.stringify({ sessionId, afterSeq }) }),
  events: (sessionId?: string, afterSeq = 0, signal?: AbortSignal) => apiRequest(`/recorder/events?afterSeq=${afterSeq}${sessionId ? `&sessionId=${encodeURIComponent(sessionId)}` : ''}`, { signal }),
  status: () => apiRequest('/recorder/status'),
}

// ==================== 访问鉴权 API ====================
export const securityApi = {
  status: () => apiRequest<{ enabled: boolean; isLocal: boolean; token: string | null }>('/security/status'),
  toggle: (enabled: boolean) =>
    apiRequest<{ success: boolean; enabled?: boolean; error?: string }>(
      '/security/toggle', { method: 'POST', body: JSON.stringify({ enabled }) }
    ),
  regenerate: () =>
    apiRequest<{ success: boolean; token?: string; error?: string }>(
      '/security/regenerate', { method: 'POST' }
    ),
}

// ==================== 自定义模块 API ====================
export const customModulesApi = {
  list: (params?: { category?: string; search?: string }) =>
    apiRequest(`/custom-modules${params ? `?${new URLSearchParams(params as any).toString()}` : ''}`),
  get: (id: string) => apiRequest(`/custom-modules/${id}`),
  create: (data: any) =>
    apiRequest('/custom-modules', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: any) =>
    apiRequest(`/custom-modules/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) =>
    apiRequest(`/custom-modules/${id}`, { method: 'DELETE' }),
  duplicate: (id: string, newName?: string) =>
    apiRequest(`/custom-modules/${id}/duplicate`, {
      method: 'POST',
      body: JSON.stringify(newName ? { new_name: newName } : {}),
    }),
  importModule: (data: any) =>
    apiRequest(`/custom-modules/import`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  incrementUsage: (id: string) =>
    apiRequest(`/custom-modules/${id}/increment-usage`, { method: 'POST' }),
}


// ==================== 凭据库 API ====================
export interface CredentialItem {
  name: string
  description: string
  fields: { key: string; masked: string }[]
  created_at: string
  updated_at: string
}
export const credentialApi = {
  list: () => apiRequest<{ success: boolean; credentials: CredentialItem[] }>('/credentials'),
  names: () => apiRequest<{ success: boolean; names: string[] }>('/credentials/names'),
  upsert: (name: string, fields: Record<string, string>, description?: string) =>
    apiRequest('/credentials', {
      method: 'POST',
      body: JSON.stringify({ name, fields, description: description || '' }),
    }),
  rename: (oldName: string, newName: string) =>
    apiRequest('/credentials/rename', {
      method: 'POST',
      body: JSON.stringify({ old_name: oldName, new_name: newName }),
    }),
  delete: (name: string) =>
    apiRequest(`/credentials/${encodeURIComponent(name)}`, { method: 'DELETE' }),
}

// ==================== 留存清理 API ====================
export interface RetentionConfig {
  enabled: boolean
  recordings_max_days: number
  recordings_max_total_mb: number
  data_max_days: number
  data_max_total_mb: number
  cleanup_interval_hours: number
}
export interface RetentionUsage {
  recordings: { count: number; sizeMB: number }
  data: { count: number; sizeMB: number }
}
export const retentionApi = {
  getConfig: () =>
    apiRequest<{ success: boolean; config: RetentionConfig; usage: RetentionUsage }>('/retention/config'),
  setConfig: (config: Partial<RetentionConfig>) =>
    apiRequest<{ success: boolean; config: RetentionConfig }>('/retention/config', {
      method: 'POST',
      body: JSON.stringify(config),
    }),
  cleanup: () => apiRequest('/retention/cleanup', { method: 'POST' }),
  usage: () => apiRequest<{ success: boolean; usage: RetentionUsage }>('/retention/usage'),
}

// ==================== 工作流整包 API ====================
export const workflowBundleApi = {
  export: (name: string, content: { nodes: unknown[]; edges: unknown[]; variables?: unknown[] }) =>
    apiRequest<{ success: boolean; bundle?: unknown; error?: string }>('/workflow-bundle/export', {
      method: 'POST',
      body: JSON.stringify({ name, content }),
    }),
  import: (bundle: unknown) =>
    apiRequest<{
      success: boolean
      name?: string
      workflow?: { nodes: unknown[]; edges: unknown[]; variables: unknown[] }
      restored?: { customModules: number; images: number }
      error?: string
    }>('/workflow-bundle/import', {
      method: 'POST',
      body: JSON.stringify({ bundle }),
    }),
}


// ==================== 插件市场 API ====================
export interface PluginInfo {
  id: string
  name: string
  version?: string
  author?: string
  description?: string
  homepage?: string
  keywords?: string[]
  enabled?: boolean
  official?: boolean
  moduleIds?: string[]
}

export const pluginApi = {
  installed: () =>
    apiRequest<{ success: boolean; plugins: PluginInfo[] }>('/plugins/installed'),
  market: () =>
    apiRequest<{ success: boolean; source?: string; plugins: PluginInfo[] }>('/plugins/market'),
  getMarketUrl: () => apiRequest<{ success: boolean; url: string }>('/plugins/market-url'),
  setMarketUrl: (url: string) =>
    apiRequest<{ success: boolean }>('/plugins/market-url', { method: 'POST', body: JSON.stringify({ url }) }),
  installPackage: (pkg: unknown) =>
    apiRequest<{ success: boolean; id?: string; moduleCount?: number; error?: string }>(
      '/plugins/install', { method: 'POST', body: JSON.stringify({ package: pkg }) }
    ),
  installFromMarket: (pluginId: string) =>
    apiRequest<{ success: boolean; error?: string }>(`/plugins/install-from-market/${encodeURIComponent(pluginId)}`, { method: 'POST' }),
  setEnabled: (pluginId: string, enabled: boolean) =>
    apiRequest<{ success: boolean; enabled?: boolean; error?: string }>(
      `/plugins/${encodeURIComponent(pluginId)}/enable`, { method: 'POST', body: JSON.stringify({ enabled }) }
    ),
  uninstall: (pluginId: string) =>
    apiRequest<{ success: boolean; error?: string }>(`/plugins/${encodeURIComponent(pluginId)}`, { method: 'DELETE' }),
  exportPackage: (pluginId: string) =>
    apiRequest<{ success: boolean; package?: unknown; error?: string }>(
      `/plugins/${encodeURIComponent(pluginId)}/export`
    ),
  publish: (pluginId: string, hubUrl?: string) =>
    apiRequest<{ success: boolean; published?: boolean; package?: unknown; exportedPath?: string; error?: string }>(
      `/plugins/${encodeURIComponent(pluginId)}/publish`, { method: 'POST', body: JSON.stringify({ hubUrl: hubUrl || '' }) }
    ),
  getReviews: (pluginId: string) =>
    apiRequest<{ success: boolean; reviews: PluginReview[]; summary: { count: number; average: number } }>(
      `/plugins/${encodeURIComponent(pluginId)}/reviews`
    ),
  addReview: (pluginId: string, rating: number, comment?: string, user?: string) =>
    apiRequest<{ success: boolean; review?: PluginReview; summary?: { count: number; average: number }; error?: string }>(
      `/plugins/${encodeURIComponent(pluginId)}/reviews`,
      { method: 'POST', body: JSON.stringify({ rating, comment: comment || '', user: user || '匿名用户' }) }
    ),
}

export interface PluginReview {
  id: string
  user: string
  rating: number
  comment: string
  createdAt: string
}


// ==================== 赞助与致谢 API ====================
export interface SponsorItem {
  name: string
  date?: string
  amount?: string
}
export const sponsorApi = {
  /** 赞助者名单（从 README 解析，随版本更新，非实时） */
  list: () => apiRequest<{ sponsors: SponsorItem[]; count: number }>('/sponsors/list'),
  /** 收款码是否已配置 */
  status: () => apiRequest<{ wechat: boolean; alipay: boolean }>('/sponsors/status'),
  /** 收款码图片直链（带时间戳避免缓存旧图） */
  qrUrl: (kind: 'wechat' | 'alipay') => `${getBackendUrl()}/api/sponsors/qr/${kind}?t=${Date.now()}`,
}

// ==================== 功能模块包（模块化分发体系） ====================

export interface FeaturePackInfo {
  id: string
  name: string
  description: string
  category: string
  size_mb: number
  recommended: boolean
  note: string
  download_url: string
  module_categories: string[]
  module_types: string[]
  installed: boolean
  install_record: { installed_at?: string; version?: string; file_count?: number } | null
}

export const featurePackApi = {
  /** 全部功能包清单 + 安装状态 */
  list: () => apiRequest<{ success: boolean; packs: FeaturePackInfo[] }>('/feature-packs'),
  /** 从本地文件路径安装（后端直接读文件，适合大包） */
  installFromPath: (path: string) =>
    apiRequest<{ success: boolean; id?: string; name?: string; installed_files?: number; warning?: string }>(
      '/feature-packs/install-path', { method: 'POST', body: JSON.stringify({ path }) }
    ),
  /** 上传 zip 安装（适合小包） */
  installUpload: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiRequest<{ success: boolean; id?: string; name?: string; installed_files?: number; warning?: string }>(
      '/feature-packs/install', { method: 'POST', body: formData }
    )
  },
  /** 工作流运行前预检：返回缺失功能包清单与格式化提示 */
  preflight: (moduleTypes: string[]) =>
    apiRequest<{ success: boolean; ok: boolean; missing: Array<{ alternatives: Array<{ id: string; name: string; size_mb: number; download_url?: string }>; module_types: string[] }>; message: string }>(
      '/feature-packs/preflight', { method: 'POST', body: JSON.stringify({ module_types: moduleTypes }) }
    ),
  /** 卸载功能包 */
  uninstall: (id: string) =>
    apiRequest<{ success: boolean; removed?: number }>(
      '/feature-packs/uninstall', { method: 'POST', body: JSON.stringify({ id }) }
    ),
  /** 查询某模块类型依赖的功能包 */
  moduleHint: (moduleType: string) =>
    apiRequest<{ success: boolean; pack: { id: string; name: string; installed: boolean } | null }>(
      `/feature-packs/module-hint/${encodeURIComponent(moduleType)}`
    ),
}
