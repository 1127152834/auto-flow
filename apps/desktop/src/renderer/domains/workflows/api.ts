import {useGlobalConfigStore} from './hooks/stores/globalConfigStore'
import {requestSessionTransition} from './lib/documentLeave'
import { checkedRetention } from './lib/retentionContract'
import {checkedCredentialFields, checkedCredentialWrite} from './lib/credentialContract'
import {checkedImageWrite} from './lib/imageAssetContract'
import {checkedPathSelection} from './lib/pathSelectionContract'
import {sendDebugControl,sendDebugVariables} from './api/debugControl'
import { checkedExecutionLogPage, checkedWorkflowRunPage } from './lib/executionLogContract'
import type {DebugControlRequest,DebugVariablesRequest} from './lib/debugControlContract'
// Source: WebRPA@5ccb900e, services/api.ts; see SOURCE.md for license and adaptation boundaries.
import type { components } from '../../shared/api/generated'
import { getStudioTransportRevision, studioFetch } from './api/transport'
import { getBackendBaseUrl } from './api/config'
import { parseApiWireError, type ApiWireError } from '../../shared/api/client'

// 获取后端 API 基础地址
function getApiBase(): string {
  return `${getBackendBaseUrl()}/api`
}



// 兼容旧调用入口；地址现在在每次请求时读取，不缓存旧连接。
export function updateApiBase() {
  getApiBase()
}

// 获取当前 API 基础地址
export function getApiBaseUrl(): string {
  return getApiBase()
}

// 获取后端服务 URL（不含 /api 前缀）
export function getBackendUrl(): string {
  return getBackendBaseUrl()
}

export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: string
  httpStatus?: number
  errorDetails?: ApiWireError
  outcomeUnknown?: boolean
}

export type WorkflowRunSummary = components['schemas']['StudioWorkflowRunSummary']
export type WorkflowRunPage = components['schemas']['StudioWorkflowRunPage']
export type ExecutionLogPage = components['schemas']['StudioExecutionLogPage']
export type ModelOptionList = components['schemas']['ModelOptionListRead']
export interface ExecutionLogQuery {
  cursor?: number
  limit?: number
  query?: string
  levels?: string[]
  nodeId?: string
  executionId?: string
}

function executionLogSearch(query: ExecutionLogQuery = {}): string {
  const params = new URLSearchParams()
  if (query.cursor !== undefined) params.set('cursor', String(query.cursor))
  if (query.limit !== undefined) params.set('limit', String(query.limit))
  if (query.query?.trim()) params.set('query', query.query.trim())
  if (query.levels?.length) params.set('levels', query.levels.join(','))
  if (query.nodeId?.trim()) params.set('nodeId', query.nodeId.trim())
  if (query.executionId?.trim()) params.set('executionId', query.executionId.trim())
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
}

// 调用 API 请求
export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  try {
    // 连接在挂载 Studio 前已配置；同步选定地址并发起传输，避免切换连接后错发写请求。
    const url = `${getApiBase()}${endpoint}`
    const isFormData = options.body instanceof FormData
    const response = await studioFetch(url, {
      ...options,
      headers: isFormData
        ? { ...(options.headers as Record<string, string>) }
        : { 'Content-Type': 'application/json', ...(options.headers as Record<string, string>) },
    })
    if (!response.ok) {
      // 尝试解析后端返回的详细错误信息（FastAPI 422 的 detail 字段）
      let detailMessage = ''
      let errorDetails: ApiWireError | undefined
      try {
        const errBody = await response.json()
        if (errBody) {
          errorDetails = parseApiWireError(errBody)
          if (errorDetails) {
            detailMessage = errorDetails.message
          } else if (typeof errBody.detail === 'string') {
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
      return { success: false, httpStatus: response.status, error: detailMessage ? `${baseError} - ${detailMessage}` : baseError, ...(errorDetails ? { errorDetails } : {}) }
    }
    if (response.status === 204) return { success: true }
    const data = await response.json()
    // Frozen WebRPA dialog cancellation is a successful read with no selection.
    if (['/system/select-file', '/system/select-folder'].includes(endpoint) && data?.success === false && data.path === null && !data.error && data.message === '用户取消选择') {
      return { success: true, data }
    }
    if (data && !Array.isArray(data) && data.success === false) {
      const message = [data.error, data.message, data.detail].find(value => typeof value === 'string' && value.trim())
      return { success: false, error: message || '操作失败，服务未提供具体原因' }
    }
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
  selectFolder: async (title?: string, initialDir?: string) =>
    checkedPathSelection(await apiRequest<unknown>('/system/select-folder', {
      method: 'POST', body: JSON.stringify({title,initialDir} satisfies Partial<components['schemas']['StudioFolderSelectRequest']>),
    })),
  selectFile: async (title?: string, initialDir?: string, fileTypes?: Array<[string, string]>) =>
    checkedPathSelection(await apiRequest<unknown>('/system/select-file', {
      method: 'POST', body: JSON.stringify({title,initialDir,fileTypes} satisfies Partial<components['schemas']['StudioFileSelectRequest']>),
    })),
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

export const modelApi = {
  listOptions: () => apiRequest<ModelOptionList>('/v1/models/options'),
}

// ==================== 工作流 API ====================
const workflowRevisions = new Map<string, number>()
const pendingWorkflowWrites = new Map<string, string>()

function workflowWriteKey(operation: string, payload: unknown): string {
  return `${operation}:${JSON.stringify(payload)}`
}

function workflowRequestId(key: string, supplied?: unknown): string {
  if (typeof supplied === 'string' && supplied.trim()) return supplied
  const existing = pendingWorkflowWrites.get(key)
  if (existing) return existing
  const requestId = crypto.randomUUID()
  pendingWorkflowWrites.set(key, requestId)
  return requestId
}

function rememberWorkflow(value: unknown, fallbackRevision?: number): void {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return
  const item = value as Record<string, unknown>
  if (typeof item.id !== 'string' || !item.id) return
  const revision = Number.isSafeInteger(item.revision) && Number(item.revision) > 0
    ? Number(item.revision)
    : fallbackRevision
  if (revision) workflowRevisions.set(item.id, revision)
}

function settleWorkflowWrite(key: string, result: ApiResponse<unknown>): void {
  if (result.success || (result.httpStatus !== undefined && result.httpStatus >= 400 && result.httpStatus < 500)) {
    pendingWorkflowWrites.delete(key)
  }
}

export const workflowApi = {
  list: async () => {
    const result = await apiRequest<any[]>('/workflows')
    result.data?.forEach(item => rememberWorkflow(item, 1))
    return result
  },
  get: async (id: string) => {
    const result = await apiRequest<any>(`/workflows/${id}`)
    if (result.success) rememberWorkflow(result.data, 1)
    return result
  },
  create: async (data: any) => {
    const key = workflowWriteKey('create', data)
    const clientRequestId = workflowRequestId(key, data?.clientRequestId)
    const result = await apiRequest<any>('/workflows', {
      method: 'POST', body: JSON.stringify({...data, clientRequestId}),
    })
    if (result.success) rememberWorkflow(result.data, 1)
    settleWorkflowWrite(key, result)
    return result
  },
  update: async (id: string, data: any) => {
    const expectedRevision = Number.isSafeInteger(data?.expectedRevision)
      ? data.expectedRevision
      : workflowRevisions.get(id) ?? (Number.isSafeInteger(data?.revision) ? data.revision : 1)
    const key = workflowWriteKey(`update:${id}:${expectedRevision}`, data)
    const clientRequestId = workflowRequestId(key, data?.clientRequestId)
    const result = await apiRequest<any>(`/workflows/${id}`, {
      method: 'PUT',
      body: JSON.stringify({...data, expectedRevision, clientRequestId}),
    })
    if (result.success) rememberWorkflow(result.data, expectedRevision + 1)
    settleWorkflowWrite(key, result)
    return result
  },
  delete: (id: string) => {
    const expectedRevision = workflowRevisions.get(id) ?? 1
    return apiRequest(`/workflows/${id}?expectedRevision=${expectedRevision}`, { method: 'DELETE' })
  },
  execute: (id: string, params?: any) =>
    apiRequest(`/workflows/${id}/execute`, { method: 'POST', body: JSON.stringify(params || {}) }),
  stop: (id: string, runId?:string) =>
    apiRequest(`/workflows/${id}/stop`, { method: 'POST', body:JSON.stringify({runId}) }),
  getRun: (runId:string) => apiRequest<components['schemas']['StudioWorkflowRunSummary']>(`/workflow-runs/${encodeURIComponent(runId)}`),
  /** 调试：从暂停处继续 */
  debugResume: (id: string, context: DebugControlRequest) =>
    sendDebugControl(id,'resume',context),
  /** 调试：单步执行 */
  debugStep: (id: string, context: DebugControlRequest) =>
    sendDebugControl(id,'step',context),
  /** 调试：运行中更新断点 */
  debugBreakpoints: (id: string, breakpoints: string[]) =>
    apiRequest(`/workflows/${id}/debug/breakpoints`, { method: 'POST', body: JSON.stringify({ breakpoints }) }),
  debugVariables: (id: string, request: DebugVariablesRequest) => sendDebugVariables(id, request),
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
  listRuns: (documentId?: string, cursor = 0, limit = 20) => {
    const params = new URLSearchParams({ cursor: String(cursor), limit: String(limit) })
    if (documentId?.trim()) params.set('documentId', documentId.trim())
    return checkedWorkflowRunPage(apiRequest<unknown>(`/workflow-runs?${params.toString()}`))
  },
  getRunLogs: (runId: string, query: ExecutionLogQuery = {}) =>
    checkedExecutionLogPage(apiRequest<unknown>(`/workflow-runs/${encodeURIComponent(runId)}/logs${executionLogSearch(query)}`), runId),
  getRunResults: async (runId:string,cursor=0,limit=100,throughSequence?:number) => {
    const params=new URLSearchParams({cursor:String(cursor),limit:String(limit)})
    if(throughSequence!==undefined)params.set('throughSequence',String(throughSequence))
    type Page=components['schemas']['StudioRunResultPage']
    const result=await apiRequest<Page>(`/workflow-runs/${encodeURIComponent(runId)}/results?${params}`)
    if(!result.success)return result
    const page=result.data
    if(!page||page.runId!==runId||!Array.isArray(page.items)||!Number.isSafeInteger(page.total)||page.total<0||!Number.isSafeInteger(page.throughSequence)||page.throughSequence<0||page.items.length>limit||page.items.length>page.total||page.items.some((row,index)=>!row||!Number.isSafeInteger(row.sequence)||row.sequence<1||row.sequence>page.throughSequence||(index>0&&row.sequence<=page.items[index-1].sequence)||typeof row.nodeId!=='string'||typeof row.executionId!=='string'||!row.values||Array.isArray(row.values)||typeof row.values!=='object'||!row.largeValues||Array.isArray(row.largeValues)||typeof row.largeValues!=='object'||Object.values(row.largeValues).some(value=>typeof value!=='string'))||(throughSequence!==undefined&&page.throughSequence!==throughSequence)||(page.nextCursor!==null&&(!Number.isSafeInteger(page.nextCursor)||page.nextCursor<=cursor)))return {success:false,error:'运行结果页身份或分页结构无效'} as ApiResponse<Page>
    return result
  },
  getRunResultValue:async(runId:string,sequence:number,key:string)=>{
    type Value=components['schemas']['StudioRunResultValue']
    const result=await apiRequest<Value>(`/workflow-runs/${encodeURIComponent(runId)}/results/${sequence}/value?${new URLSearchParams({key})}`)
    if(result.success&&(!result.data||result.data.runId!==runId||result.data.sequence!==sequence||result.data.key!==key||!Object.hasOwn(result.data,'value')))return {success:false,error:'结果值不属于请求的运行或字段'} as ApiResponse<Value>
    return result
  },
  exportRunResults:async(runId:string,throughSequence:number)=>{
    try{
      const result=await studioFetch(`${getApiBase()}/workflow-runs/${encodeURIComponent(runId)}/results/export?throughSequence=${throughSequence}`)
      if(!result.ok)return {success:false,error:`结果导出失败：HTTP ${result.status}`} as ApiResponse<Blob>
      return {success:true,data:await result.blob()} as ApiResponse<Blob>
    }catch(error){return {success:false,error:String(error)} as ApiResponse<Blob>}
  },
  exportRunLogs: async (runId: string, query: Omit<ExecutionLogQuery, 'cursor' | 'limit'> = {}) => {
    try {
      const response = await studioFetch(`${getApiBase()}/workflow-runs/${encodeURIComponent(runId)}/logs/export${executionLogSearch(query)}`)
      if (!response.ok) return { success: false, httpStatus: response.status, error: `HTTP ${response.status}: ${response.statusText}` } as ApiResponse<Blob>
      return { success: true, data: await response.blob() } as ApiResponse<Blob>
    } catch (error) {
      return { success: false, error: error instanceof Error ? error.message : '日志导出失败' } as ApiResponse<Blob>
    }
  },
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
  list: () => apiRequest<components['schemas']['StudioImageAsset'][]>('/image-assets'),
  listFolders: () => apiRequest<string[]>('/image-assets/folders'),
  get: (id: string) => apiRequest<components['schemas']['StudioImageAsset']>(`/image-assets/${id}`),
  upload: (file: File, folder?: string) => {
      const formData = new FormData()
      formData.append('file', file)
    if (folder) formData.append('folder', folder)
    return checkedImageWrite(apiRequest<components['schemas']['StudioImageUploadResult']>('/image-assets/upload', { method: 'POST', body: formData }), 'asset', false)
  },
  delete: (id: string) => checkedImageWrite(apiRequest<components['schemas']['StudioImageMutationResult']>(`/image-assets/${id}`, { method: 'DELETE' })),
  createFolder: (name: string, parentPath?: string) =>
    checkedImageWrite(apiRequest<components['schemas']['StudioImageFolderCreated']>('/image-assets/folders', { method: 'POST', body: JSON.stringify({ name, parentPath }) }), 'path'),
  renameFolder: (oldPath: string, newName: string) =>
    checkedImageWrite(apiRequest<components['schemas']['StudioImageFolderRenamed']>('/image-assets/folders/rename', { method: 'PUT', body: JSON.stringify({ oldPath, newName }) }), 'newPath'),
  deleteFolder: (folderPath: string) =>
    checkedImageWrite(apiRequest<components['schemas']['StudioImageFolderDeleted']>('/image-assets/folders', { method: 'DELETE', body: JSON.stringify({ folderPath }) }), 'deletedCount'),
  rename: (assetId: string, newName: string) =>
    checkedImageWrite(apiRequest<components['schemas']['StudioImageRenameResult']>(`/image-assets/${assetId}/rename?newName=${encodeURIComponent(newName)}`, { method: 'PUT' }), 'asset'),
  moveAsset: (assetId: string, targetFolder?: string) =>
    checkedImageWrite(apiRequest<components['schemas']['StudioImageMoved']>('/image-assets/move', { method: 'PUT', body: JSON.stringify({ assetId, targetFolder }) }), 'newFolder'),
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
  execute: (id: string, commandId: string) =>
    apiRequest(`/scheduled-tasks/${id}/execute`, { method: 'POST', body: JSON.stringify({ commandId }) }),
  getCommand: (commandId: string) =>
    apiRequest(`/scheduled-tasks/commands/${encodeURIComponent(commandId)}`),
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
let browserSession:{id:string;connection:number;profileId?:string;unconfirmed?:boolean;starting?:string}|null=null
let browserStatusRequest=0
let browserPageIdentity:string|null=null
export function currentBrowserSession(){
 if(browserSession?.connection!==getStudioTransportRevision()){browserSession=null;browserPageIdentity=null}
 return browserSession?.id??null
}
type BrowserPages = components['schemas']['StudioBrowserPages']
async function browserPagesRequest(options?:RequestInit):Promise<ApiResponse<BrowserPages>> {
  const revision=getStudioTransportRevision()
  if(options)browserStatusRequest++
  const request=browserStatusRequest
  const result=await apiRequest<BrowserPages>('/browser/pages',options)
  if(revision!==getStudioTransportRevision())return {success:false,error:'浏览器所属服务已变更，响应未应用'}
  if(request!==browserStatusRequest)return {success:false,error:'浏览器页面查询已过期，未应用旧状态'}
  if(!result.success)return result
  const data=result.data
  if(!data || typeof data.sessionId!=='string' || !data.sessionId || !Number.isSafeInteger(data.revision) || data.revision<0 || !Array.isArray(data.pages) || data.pages.some(page=>!page || typeof page.pageId!=='string' || !page.pageId || typeof page.url!=='string' || typeof page.title!=='string') || new Set(data.pages.map(page=>page.pageId)).size!==data.pages.length || (data.targetPageId!==null&&!data.pages.some(page=>page.pageId===data.targetPageId)))return {success:false,error:'浏览器页面列表结构或目标身份无效'}
  const pageIdentity=`${revision}:${data.sessionId}:${data.revision}`
  if(browserPageIdentity!==null&&browserPageIdentity!==pageIdentity)browserStatusRequest++
  browserPageIdentity=pageIdentity
  browserSession={id:data.sessionId,connection:revision,starting:browserSession?.starting,profileId:browserSession?.profileId}
  return result
}

export const browserApi = {
  profiles: async () => {
    const result=await apiRequest<components['schemas']['ProfileList']>('/v1/profiles')
    if(!result.success)return result
    if(!result.data||!Array.isArray(result.data.items)||!result.data.items.every(profile=>profile&&typeof profile.id==='string'&&profile.id&&typeof profile.name==='string'))return {success:false,error:'管理端浏览器配置响应无效'} as ApiResponse<components['schemas']['ProfileList']>
    return result
  },
  resolveProfile: async (requestedId?:string) => {
    const revision=getStudioTransportRevision()
    const selected=requestedId??useGlobalConfigStore.getState().config.browserProfileId
    const result=await browserApi.profiles()
    if(revision!==getStudioTransportRevision())return {success:false,error:'服务已变更，未采用旧配置'} as ApiResponse<components['schemas']['ProfileRead']>
    if(!result.success||!result.data)return {success:false,error:result.error||'浏览器配置读取失败'} as ApiResponse<components['schemas']['ProfileRead']>
    const profile=selected?result.data.items.find(item=>item.id===selected):result.data.items[0]
    if(!profile)return {success:false,httpStatus:selected?404:422,error:selected?'所选浏览器配置已不可用，请重新选择':'请先在管理端创建 CloakBrowser 配置'} as ApiResponse<components['schemas']['ProfileRead']>
    return {success:true,data:profile} as ApiResponse<components['schemas']['ProfileRead']>
  },
  pages: () => browserPagesRequest(),
  page: (command:components['schemas']['StudioBrowserPageCommand']) => browserPagesRequest({method:'POST',body:JSON.stringify(command)}),
  getStatus: async () => {
    type Result = components['schemas']['StudioBrowserStatus']
    const revision=getStudioTransportRevision()
    const request=browserStatusRequest
    const result = await apiRequest<Result>('/browser/status')
    if(revision!==getStudioTransportRevision())return {success:false,error:'浏览器所属服务已变更，状态未应用'} as ApiResponse<Result>
    if(request!==browserStatusRequest)return {success:false,error:'浏览器状态查询已过期，未应用旧状态'} as ApiResponse<Result>
    if (!result.success) return result
    if (!result.data || typeof result.data.isOpen !== 'boolean' || typeof result.data.pickerActive !== 'boolean') {
      return {success:false,error:'浏览器状态响应格式错误，保留最后确认状态'} as ApiResponse<Result>
    }
    if(!result.data.isOpen){if(!browserSession?.starting)browserSession=null}
    else if(typeof result.data.sessionId==='string'&&result.data.sessionId)browserSession={id:result.data.sessionId,connection:getStudioTransportRevision(),starting:browserSession?.starting,profileId:typeof result.data?.profileId==='string'?result.data.profileId:browserSession?.profileId}
    return result
  },
  /** 检测 Playwright 内置 Chromium 是否可用（浏览器扩展兜底是否生效） */
  chromiumStatus: () => apiRequest('/browser/chromium-status'),
  open: async (url?: string, _legacyBrowserConfig?: unknown, profileId?: string) => {
    const revision=getStudioTransportRevision()
    if(browserSession?.starting)return {success:false,error:'浏览器正在启动，请等待当前请求完成'}
    browserStatusRequest++
    const operation=crypto.randomUUID()
    const provisional=!currentBrowserSession()?operation:null
    if(provisional)browserSession={id:provisional,connection:revision,unconfirmed:true}
    if(browserSession)browserSession.starting=operation
    const profile=await browserApi.resolveProfile(browserSession?.profileId??profileId)
    if(!profile.success||!profile.data){
      if(browserSession?.starting===operation)browserSession.starting=undefined
      if(browserSession?.id===provisional)browserSession=null
      return {success:false,error:profile.error,httpStatus:profile.httpStatus}
    }
    if(browserSession)browserSession.profileId=profile.data.id
    const result=await apiRequest('/browser/open', { method: 'POST', body: JSON.stringify({ url, profileId:profile.data.id }) })
    if(browserSession?.starting===operation)browserSession.starting=undefined
    if(revision!==getStudioTransportRevision())return {success:false,error:'服务连接已变更，浏览器启动结果未应用'}
    if(!result.success&&result.httpStatus&&result.httpStatus<500&&browserSession?.id===provisional)browserSession=null
    else await browserApi.getStatus()
    if(revision!==getStudioTransportRevision())return {success:false,error:'服务连接已变更，浏览器启动结果未应用'}
    return result
  },
  launch: (url?: string):Promise<ApiResponse> => browserApi.open(url),
  close: async (sessionId=currentBrowserSession()??undefined) => {
    const revision=getStudioTransportRevision()
    if(browserSession?.starting)return {success:false,error:'浏览器启动请求仍在处理中，保留占用，请稍后重试清理'}
    if(browserSession&&browserSession.id===sessionId&&browserSession.unconfirmed){
      const status=await browserApi.getStatus()
      if(revision!==getStudioTransportRevision()||!status.success)return {success:false,error:'浏览器启动结果尚未确认，保留占用，请恢复连接后重试'}
      if(status.data?.isOpen===false)return {success:true,data:{success:true}}
      if(browserSession?.unconfirmed||!currentBrowserSession())return {success:false,error:'浏览器会话身份尚未确认，未发送关闭请求'}
      sessionId=currentBrowserSession()!
    }
    browserStatusRequest++
    const result=await apiRequest('/browser/close',{method:'POST',body:JSON.stringify({sessionId})})
    if(revision!==getStudioTransportRevision())return {success:false,error:'浏览器所属服务已变更，关闭结果未应用'}
    if(result.success&&result.data?.success!==false)browserSession=null
    return result
  },
  navigate: (url: string) => {
    browserStatusRequest++
    return apiRequest('/browser/navigate', { method: 'POST', body: JSON.stringify({ url }) })
  },
  getUrl: () => apiRequest('/browser/url'),
  getSelector: (description: string) =>
    apiRequest('/browser/get-selector', { method: 'POST', body: JSON.stringify({ description }) }),
  startPicker: () => elementPickerApi.start(),
  stopPicker: () => elementPickerApi.stop(),
}

// ==================== 元素选择器 API ====================
type PickerSessionState=components['schemas']['StudioPickerSessionState']
let pickerSessionId:string|null=null
let pickerConnectionRevision=-1
export function currentPickerSession(){
  const revision=getStudioTransportRevision()
  if(revision!==pickerConnectionRevision){pickerSessionId=null;pickerConnectionRevision=revision}
  return pickerSessionId
}
function checkedPickerSession(result:ApiResponse<any>,expected:string):ApiResponse<PickerSessionState>{
  if(!result.success)return result
  const data=result.data
  if(!data || data.success!==true || data.sessionId!==expected || typeof data.active!=='boolean')return {success:false,error:'元素拾取会话响应身份或结构错误'}
  return result as ApiResponse<PickerSessionState>
}
const pickerQuery=(sessionId:string)=>`?sessionId=${encodeURIComponent(sessionId)}`
async function readPickerResult(path:string):Promise<ApiResponse<any>>{
  if(!currentPickerSession()){
    const status=await elementPickerApi.getStatus()
    if(!status.success)return status
  }
  const sessionId=currentPickerSession()
  const revision=getStudioTransportRevision()
  const pageGeneration=browserStatusRequest
  const result=await apiRequest(`${path}${sessionId?pickerQuery(sessionId):''}`)
  if(revision!==getStudioTransportRevision()||sessionId!==currentPickerSession()||pageGeneration!==browserStatusRequest)return {success:false,error:'拾取结果已过期，未应用定位信息'}
  const checked=checkedPickerSession(result,sessionId||'none')
  if(!checked.success)return checked
  const data=result.data
  if(path!=='/element-picker/similar'&&(typeof data.selected!=='boolean'||(data.selected&&(!data.active||!data.element||typeof data.element.selector!=='string'||!data.element.selector.trim()))))return {success:false,error:'拾取结果格式错误，未应用定位信息'}
  return result
}
export const elementPickerApi = {
  /**
   * 启动元素选择器
   * @param url 可选，要打开的目标页面 URL
   * 使用管理端 CloakBrowser Profile，旧启动参数不再发送。
   */
  start: async (url?: string, _legacyBrowserConfig?: unknown) => {
    const revision=getStudioTransportRevision()
    let previous=currentPickerSession()
    if(!previous&&!await requestSessionTransition(true))return {success:false,error:'已取消切换到元素拾取'}
    if(revision!==getStudioTransportRevision())return {success:false,error:'服务连接已变更，未启动拾取'}
    previous=currentPickerSession()
    const sessionId=previous||crypto.randomUUID()
    pickerSessionId=sessionId
    const provisionalBrowser=!currentBrowserSession()?crypto.randomUUID():null
    if(provisionalBrowser)browserSession={id:provisionalBrowser,connection:revision,unconfirmed:true,starting:provisionalBrowser}
    const profile=await browserApi.resolveProfile(browserSession?.profileId)
    if(!profile.success||!profile.data){
      if(!previous&&pickerSessionId===sessionId)pickerSessionId=null
      if(browserSession?.id===provisionalBrowser)browserSession=null
      return {success:false,error:profile.error,httpStatus:profile.httpStatus}
    }
    if(revision!==getStudioTransportRevision()||sessionId!==currentPickerSession())return {success:false,error:'拾取请求已取消或服务已变更'}
    if(browserSession)browserSession.profileId=profile.data.id
    let result=checkedPickerSession(await apiRequest('/element-picker/start', {
      method: 'POST',
      body: JSON.stringify({sessionId,url:url||null,profileId:profile.data.id}),
    }),sessionId)
    if(browserSession?.starting===provisionalBrowser)browserSession.starting=undefined
    if(revision!==getStudioTransportRevision()||sessionId!==currentPickerSession())return {success:false,error:'服务连接或拾取会话已变更，启动结果未应用'}
    if(!result.success&&(!result.httpStatus||result.httpStatus>=500)){
      const recovered=checkedPickerSession(await apiRequest(`/element-picker/status${pickerQuery(sessionId)}`),sessionId)
      if(revision!==getStudioTransportRevision()||sessionId!==currentPickerSession())return {success:false,error:'服务连接或拾取会话已变更，启动结果未应用'}
      if(recovered.success&&recovered.data?.active)result=recovered
      else if(recovered.httpStatus===404||recovered.httpStatus===409){
        if(!previous)pickerSessionId=null
        if(browserSession?.id===provisionalBrowser)browserSession=null
        return recovered
      }
      else if(!recovered.success)return {...result,outcomeUnknown:true}
    }
    if(!result.success&&result.httpStatus&&result.httpStatus<500&&!previous){
      pickerSessionId=null
      if(browserSession?.id===provisionalBrowser)browserSession=null
    }
    if(result.success&&!result.data?.active)return {success:false,error:'拾取会话未启动'}
    if(result.success)await browserApi.getStatus()
    if(revision!==getStudioTransportRevision()||sessionId!==currentPickerSession())return {success:false,error:'服务连接或拾取会话已变更，启动结果未应用'}
    return result
  },
  stop: async () => {
    let sessionId=currentPickerSession()
    if(!sessionId){
      const status=await elementPickerApi.getStatus()
      if(!status.success)return status
      sessionId=currentPickerSession()
    }
    if(!sessionId)return {success:true,data:{success:true,sessionId:'none',active:false} as PickerSessionState}
    const revision=getStudioTransportRevision()
    let result=checkedPickerSession(await apiRequest('/element-picker/stop',{method:'POST',body:JSON.stringify({sessionId})}),sessionId)
    if(revision!==getStudioTransportRevision()||sessionId!==currentPickerSession())return {success:false,error:'服务连接或拾取会话已变更，关闭结果未应用'}
    if(!result.success&&(!result.httpStatus||result.httpStatus>=500)){
      const recovered=checkedPickerSession(await apiRequest(`/element-picker/status${pickerQuery(sessionId)}`),sessionId)
      if(revision!==getStudioTransportRevision()||sessionId!==currentPickerSession())return {success:false,error:'服务连接或拾取会话已变更，关闭结果未应用'}
      if(recovered.success&&!recovered.data?.active)result=recovered
    }
    if(result.success&&!result.data?.active)pickerSessionId=null
    if(result.success&&result.data?.active)return {success:false,error:'拾取会话仍在清理，请重试'}
    return result
  },
  getResult: () => readPickerResult('/element-picker/result'),
  getSelected: () => readPickerResult('/element-picker/selected'),
  getSimilar: async () => {
    type Wire = components['schemas']['StudioSimilarPickerResult']
    type Similar = components['schemas']['StudioSimilarElements']
    type Result = Omit<Partial<Wire>, 'similar'> & {similar?: (Pick<Similar, 'pattern' | 'count' | 'minIndex' | 'maxIndex'> & Partial<Similar>) | null}
    const result:ApiResponse<Result> = await readPickerResult('/element-picker/similar')
    if (!result.success) return result
    const data = result.data
    const similar = data?.similar
    const integer = (value: unknown) => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
    if (!data || typeof data.selected !== 'boolean' || typeof data.active !== 'boolean' ||
        (data.selected && (!similar || typeof similar.pattern !== 'string' || !similar.pattern.includes('{index}') ||
          !integer(similar.count) || similar.count < 1 || !integer(similar.minIndex) || !integer(similar.maxIndex) || similar.maxIndex < similar.minIndex ||
          (similar.indices != null && (!Array.isArray(similar.indices) || similar.indices.some(index => !integer(index) || index < similar.minIndex || index > similar.maxIndex)))))) {
      return {success: false, error: '相似元素响应格式错误，未应用定位结果'} as ApiResponse<Result>
    }
    return result
  },
  getStatus: async () => {
    const requested=currentPickerSession()
    const revision=getStudioTransportRevision()
    const result=await apiRequest<Partial<PickerSessionState>>(`/element-picker/status${requested?pickerQuery(requested):''}`)
    if(revision!==getStudioTransportRevision()||requested!==currentPickerSession())return {success:false,error:'拾取状态响应已过期'}
    if(!result.success)return result
    if(result.data?.success!==true||typeof result.data.active!=='boolean'||typeof result.data.sessionId!=='string'||!result.data.sessionId.trim()||(requested&&result.data.sessionId!==requested))return {success:false,error:'元素拾取状态身份或结构错误'}
    if(result.data?.active){
      if(typeof result.data.sessionId!=='string'||!result.data.sessionId.trim()||(requested&&result.data.sessionId!==requested))return {success:false,error:'元素拾取状态属于其他会话'}
      pickerSessionId=result.data.sessionId;pickerConnectionRevision=getStudioTransportRevision()
    }else if(requested)pickerSessionId=null
    return result
  },
  /** 在当前浏览器页面上测试选择器是否命中并高亮匹配项 */
  testSelector: async (selector: string, hints?: Record<string, unknown>, highlight = true) => {
    type Wire = components['schemas']['StudioSelectorTestResult']
    type Result = Pick<Wire, 'success' | 'matched' | 'count'> & Partial<Omit<Wire, 'success' | 'matched' | 'count'>>
    const sessionId=currentPickerSession()
    const revision=getStudioTransportRevision()
    const pageGeneration=browserStatusRequest
    const result = await apiRequest<Result>('/element-picker/test-selector', {
      method: 'POST', body: JSON.stringify({ selector, hints: hints || null, highlight, sessionId }),
    })
    if(revision!==getStudioTransportRevision()||sessionId!==currentPickerSession()||pageGeneration!==browserStatusRequest)return {success:false,error:'定位测试响应已过期，请重新测试'}
    if (!result.success) return result
    const data = result.data
    const record = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
    const optionalString = (value: unknown) => value === undefined || value === null || typeof value === 'string'
    const validCount = (value: unknown) => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
    if (!record(data) || data.success !== true || typeof data.matched !== 'boolean' ||
        !validCount(data.count) || data.matched !== (data.count > 0) ||
        !optionalString(data.matchedSelector) || !optionalString(data.error) ||
        (data.isPrimary != null && typeof data.isPrimary !== 'boolean') ||
        (data.element != null && (!record(data.element) || !optionalString(data.element.tag) || !optionalString(data.element.text))) ||
        (data.tried != null && (!Array.isArray(data.tried) || !data.tried.every(attempt => record(attempt) &&
          typeof attempt.selector === 'string' && (attempt.count == null || validCount(attempt.count)) && optionalString(attempt.error))))) {
      return { success: false, error: '定位测试响应格式错误，请重试或检查服务连接' } as ApiResponse<Result>
    }
    return result
  },
}

// ==================== 网页智能录制器 API ====================
function validRecorderRequest(sessionId: string, afterSeq = 0): boolean {
  return typeof sessionId === 'string' && !!sessionId.trim() && Number.isSafeInteger(afterSeq) && afterSeq >= 0
}
const invalidRecorderRequest = (): Promise<ApiResponse<never>> => Promise.resolve({ success: false, error: '录制会话标识或确认游标无效' })
async function recorderRequest<T>(path:string,sessionId:string,options:RequestInit={}):Promise<ApiResponse<T>>{
  const revision=getStudioTransportRevision()
  const result=await apiRequest<T>(path,options)
  if(revision!==getStudioTransportRevision())return {success:false,error:'录制所属服务连接已变更，响应未应用'}
  if(result.success&&(result.data as any)?.sessionId!==sessionId)return {success:false,error:'录制响应不属于请求会话'}
  return result
}

async function completeRecorderTail(sessionId:string, first:ApiResponse<components['schemas']['StudioRecorderStopped']>):Promise<ApiResponse<components['schemas']['StudioRecorderStopped']>> {
  if(!first.success || !first.data?.hasMore)return first
  const body=first.data
  if(!Array.isArray(body.data?.events) || !Number.isSafeInteger(body.nextSeq) || body.nextSeq<0)return {success:false,error:'录制尾部结构无效，未确认停止，请重试'}
  const events=[...body.data.events]
  let cursor=body.nextSeq
  let more=body.hasMore
  while(more){
    const next=await recorderApi.events(sessionId,cursor)
    if(!next.success)return {...next,data:undefined}
    const page=next.data
    if(!page || !Array.isArray(page.data) || !Number.isSafeInteger(page.nextSeq) || page.nextSeq<=cursor || page.data.length!==page.nextSeq-cursor || page.data.some((event,index)=>event.sequence!==cursor+index+1))return {success:false,error:'录制尾部分页不连续，未确认停止，请重试'}
    events.push(...page.data);cursor=page.nextSeq;more=Boolean(page.hasMore)
  }
  return {...first,data:{...body,nextSeq:cursor,hasMore:false,data:{events}}}
}

export const recorderApi = {
  readReview: (documentId:string) => apiRequest<components['schemas']['StudioRecordingReview']>(`/recorder/reviews/${encodeURIComponent(documentId)}`),
  saveReview: (documentId:string,body:components['schemas']['StudioRecordingReviewWrite']) => apiRequest<components['schemas']['StudioRecordingReview']>(`/recorder/reviews/${encodeURIComponent(documentId)}`,{method:'PUT',body:JSON.stringify(body)}),
  start: async (sessionId: string):Promise<ApiResponse<components['schemas']['StudioRecorderStarted']>> => {
    if(!validRecorderRequest(sessionId))return invalidRecorderRequest()
    const revision=getStudioTransportRevision()
    const result=await recorderRequest<components['schemas']['StudioRecorderStarted']>('/recorder/start',sessionId,{method:'POST',body:JSON.stringify({sessionId})})
    if(revision!==getStudioTransportRevision())return result
    if(result.success&&result.data?.success===true&&result.data.recording===true&&Number.isSafeInteger(result.data.nextSeq)&&result.data.nextSeq>=0)return result
    if(!result.httpStatus||result.httpStatus>=500){
      const status=await recorderApi.status(sessionId)
      if(revision!==getStudioTransportRevision())return {success:false,error:'录制所属服务连接已变更，响应未应用'}
      if(status.success&&status.data?.recording)return {success:true,data:{...status.data,sessionId,success:true}}
      if(status.httpStatus===404||status.httpStatus===409)return {success:false,error:status.error,httpStatus:status.httpStatus}
      if(!status.success)return {success:false,error:result.error||'录制启动尚未确认',outcomeUnknown:true}
    }
    return {success:false,error:result.error||'服务未确认录制已启动',httpStatus:result.httpStatus}
  },
  stop: async (sessionId: string, afterSeq = 0):Promise<ApiResponse<components['schemas']['StudioRecorderStopped']>> => {
    if(!validRecorderRequest(sessionId,afterSeq))return invalidRecorderRequest()
    const revision=getStudioTransportRevision()
    const result=await recorderRequest<components['schemas']['StudioRecorderStopped']>('/recorder/stop',sessionId,{method:'POST',body:JSON.stringify({sessionId,afterSeq})})
    if(revision!==getStudioTransportRevision()||(result.httpStatus&&result.httpStatus<500&&!result.success))return result
    if(result.success)return completeRecorderTail(sessionId,result)
    const status=await recorderApi.status(sessionId)
    if(revision!==getStudioTransportRevision())return {success:false,error:'录制所属服务连接已变更，响应未应用'}
    if(status.success&&status.data&&!status.data.recording){
      const tail=await recorderApi.events(sessionId,afterSeq)
      if(tail.success&&tail.data&&Array.isArray(tail.data.data)){
        const complete=await completeRecorderTail(sessionId,{success:true,data:{...tail.data,data:{events:tail.data.data}}})
        if(complete.data?.nextSeq===status.data.nextSeq)return complete
      }
    }
    return result
  },
  events: (sessionId: string, afterSeq = 0, signal?: AbortSignal) => validRecorderRequest(sessionId, afterSeq)
    ? recorderRequest<components['schemas']['StudioRecorderBatch']>(`/recorder/events?afterSeq=${afterSeq}&sessionId=${encodeURIComponent(sessionId)}`,sessionId,{signal})
    : invalidRecorderRequest(),
  status: async (sessionId?:string):Promise<ApiResponse<components['schemas']['StudioRecorderStatus']>> => {
    if(sessionId!==undefined&&!validRecorderRequest(sessionId))return invalidRecorderRequest()
    const revision=getStudioTransportRevision()
    const result=await apiRequest<components['schemas']['StudioRecorderStatus']>(`/recorder/status${sessionId?`?sessionId=${encodeURIComponent(sessionId)}`:''}`)
    if(revision!==getStudioTransportRevision())return {success:false,error:'录制所属服务连接已变更，响应未应用'}
    if(!result.success)return result
    const data=result.data
    if(!data||data.success!==true||typeof data.recording!=='boolean'||!Number.isSafeInteger(data.nextSeq)||data.nextSeq<0||
      (data.sessionId!==null&&(typeof data.sessionId!=='string'||!data.sessionId.trim()))||
      ((data.recording||data.nextSeq>0)&&!data.sessionId)||(sessionId&&data.sessionId!==sessionId))return {success:false,error:'录制状态身份或结构错误'}
    return result
  },
}

// ==================== 自定义模块 API ====================
const customModuleRevisions = new Map<string, number>()
const pendingCustomModuleWrites = new Map<string, string>()

function customModuleWriteKey(operation: string, payload: unknown): string {
  return `${operation}:${JSON.stringify(payload)}`
}

function customModuleRequestId(key: string, supplied?: unknown): string {
  if (typeof supplied === 'string' && supplied.trim()) return supplied
  const existing = pendingCustomModuleWrites.get(key)
  if (existing) return existing
  const requestId = crypto.randomUUID()
  pendingCustomModuleWrites.set(key, requestId)
  return requestId
}

function rememberCustomModule(value: unknown, fallbackRevision?: number): void {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return
  const module = value as Record<string, unknown>
  if (typeof module.id !== 'string' || !module.id) return
  const revision = Number.isSafeInteger(module.revision) && Number(module.revision) > 0
    ? Number(module.revision)
    : fallbackRevision
  if (revision) customModuleRevisions.set(module.id, revision)
}

function settleCustomModuleWrite(key: string, result: ApiResponse<unknown>): void {
  if (result.success || (result.httpStatus !== undefined && result.httpStatus >= 400 && result.httpStatus < 500)) {
    pendingCustomModuleWrites.delete(key)
  }
}

export const customModulesApi = {
  list: async (params?: { category?: string; search?: string }) => {
    const result = await apiRequest<any>(`/custom-modules${params ? `?${new URLSearchParams(params as any).toString()}` : ''}`)
    result.data?.modules?.forEach((module: unknown) => rememberCustomModule(module, 1))
    return result
  },
  get: async (id: string) => {
    const result = await apiRequest<any>(`/custom-modules/${id}`)
    if (result.success) rememberCustomModule(result.data, 1)
    return result
  },
  create: async (data: any) => {
    const key = customModuleWriteKey('create', data)
    const clientRequestId = customModuleRequestId(key, data?.clientRequestId)
    const result = await apiRequest<any>('/custom-modules', {
      method: 'POST', body: JSON.stringify({ ...data, clientRequestId }),
    })
    if (result.success) rememberCustomModule(result.data, 1)
    settleCustomModuleWrite(key, result)
    return result
  },
  update: async (id: string, data: any, suppliedRevision?: number) => {
    const expectedRevision = Number.isSafeInteger(suppliedRevision) && Number(suppliedRevision) > 0
      ? Number(suppliedRevision)
      : Number.isSafeInteger(data?.expectedRevision) && Number(data.expectedRevision) > 0
        ? Number(data.expectedRevision)
        : customModuleRevisions.get(id) ?? 1
    const key = customModuleWriteKey(`update:${id}:${expectedRevision}`, data)
    const clientRequestId = customModuleRequestId(key, data?.clientRequestId)
    const result = await apiRequest<any>(`/custom-modules/${id}`, {
      method: 'PUT', body: JSON.stringify({ ...data, expectedRevision, clientRequestId }),
    })
    if (result.success) rememberCustomModule(result.data, expectedRevision + 1)
    settleCustomModuleWrite(key, result)
    return result
  },
  delete: async (id: string, suppliedRevision?: number) => {
    const expectedRevision = Number.isSafeInteger(suppliedRevision) && Number(suppliedRevision) > 0
      ? Number(suppliedRevision)
      : customModuleRevisions.get(id) ?? 1
    const key = customModuleWriteKey(`delete:${id}:${expectedRevision}`, {})
    const clientRequestId = customModuleRequestId(key)
    const query = new URLSearchParams({ expectedRevision: String(expectedRevision), clientRequestId })
    const result = await apiRequest(`/custom-modules/${id}?${query}`, { method: 'DELETE' })
    if (result.success) customModuleRevisions.delete(id)
    settleCustomModuleWrite(key, result)
    return result
  },
  duplicate: async (id: string, newName?: string) => {
    const data = newName ? { new_name: newName } : {}
    const key = customModuleWriteKey(`duplicate:${id}`, data)
    const clientRequestId = customModuleRequestId(key)
    const result = await apiRequest<any>(`/custom-modules/${id}/duplicate`, {
      method: 'POST',
      body: JSON.stringify({ ...data, clientRequestId }),
    })
    if (result.success) rememberCustomModule(result.data, 1)
    settleCustomModuleWrite(key, result)
    return result
  },
  importModule: async (data: any) => {
    const key = customModuleWriteKey('import', data)
    const clientRequestId = customModuleRequestId(key, data?.clientRequestId)
    const result = await apiRequest<any>(`/custom-modules/import`, {
      method: 'POST',
      body: JSON.stringify({ ...data, clientRequestId }),
    })
    if (result.success) rememberCustomModule(result.data, 1)
    settleCustomModuleWrite(key, result)
    return result
  },
  incrementUsage: (id: string) =>
    apiRequest(`/custom-modules/${id}/increment-usage`, { method: 'POST' }),
}


// ==================== 凭据库 API ====================
export type CredentialItem = components['schemas']['StudioCredentialItem']
export type CredentialFieldsCommand = components['schemas']['StudioCredentialFieldsCommand']
export const credentialApi = {
  mutateFields: (command: CredentialFieldsCommand) =>
    checkedCredentialFields(apiRequest<components['schemas']['StudioCredentialFieldsConfirmed']>('/credentials/fields', { method: 'POST', body: JSON.stringify(command) }), command),
  list: () => apiRequest<components['schemas']['StudioCredentialList']>('/credentials'),
  names: () => apiRequest<components['schemas']['StudioCredentialNames']>('/credentials/names'),
  upsert: (name: string, fields: Record<string, string>, description?: string) =>
    checkedCredentialWrite(apiRequest<components['schemas']['StudioCredentialSaved']>('/credentials', {
      method: 'POST',
      body: JSON.stringify({ name, fields, description: description || '' } satisfies components['schemas']['StudioCredentialUpsertRequest']),
    }), name.trim()),
  rename: (oldName: string, newName: string) =>
    checkedCredentialWrite(apiRequest<components['schemas']['StudioCredentialConfirmed']>('/credentials/rename', {
      method: 'POST',
      body: JSON.stringify({ old_name: oldName, new_name: newName } satisfies components['schemas']['StudioCredentialRenameRequest']),
    })),
  delete: (name: string) =>
    checkedCredentialWrite(apiRequest<components['schemas']['StudioCredentialConfirmed']>(`/credentials/${encodeURIComponent(name)}`, { method: 'DELETE' })),
}

// ==================== 留存清理 API ====================
export type { RetentionConfig, RetentionUsage } from './lib/retentionContract'
export const retentionApi = {
  getConfig: () => checkedRetention(apiRequest<components['schemas']['StudioRetentionLoaded']>('/retention/config'), 'load'),
  setConfig: (config: import('./lib/retentionContract').RetentionConfig) =>
    checkedRetention(apiRequest<components['schemas']['StudioRetentionSaved']>('/retention/config', {
      method: 'POST', body: JSON.stringify(config),
    }), 'save'),
  cleanup: () => checkedRetention(apiRequest<components['schemas']['StudioRetentionCleanup']>('/retention/cleanup', { method: 'POST' }), 'cleanup'),
  usage: () => checkedRetention(apiRequest<components['schemas']['StudioRetentionUsageResponse']>('/retention/usage'), 'usage'),
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

export const inputPromptApi = {
  getState: (requestId: string) => apiRequest<components['schemas']['StudioInputPromptState']>(`/events/input-prompts/${encodeURIComponent(requestId)}`),
}

async function getClaimedRequestState(endpoint: string, requestId: string, label: string) {
  const result = await apiRequest<components['schemas']['StudioClaimedRequestState']>(`${endpoint}/${encodeURIComponent(requestId)}`)
  if (!result.success) return result
  const state = result.data
  if (!state || state.requestId !== requestId || typeof state.workflowId !== 'string' || !state.workflowId
    || typeof state.nodeId !== 'string' || !state.nodeId || !['pending','claimed','completed','failed','expired'].includes(state.status)
    || (state.status === 'claimed' && (typeof state.claimId !== 'string' || !state.claimId))) {
    return { success: false, httpStatus: 200, error: `${label}请求状态无效，未执行${label}` }
  }
  return result
}

export const jsScriptApi = {
  getState: (requestId: string) => getClaimedRequestState('/events/js-requests',requestId,'脚本'),
}
export const speechApi = {
  getState: (requestId: string) => getClaimedRequestState('/events/tts-requests',requestId,'语音'),
}
export const desktopActionApi = {
  getState: (requestId: string) => getClaimedRequestState('/events/desktop-actions', requestId, '平台操作'),
}


export type VariableTrackingRecord = components['schemas']['StudioVariableTrackingRecord']
export type RunVariableTrackingRecord = components['schemas']['StudioRunVariableTrackingRecord']
export interface RunTrackingQuery { cursor?:number; limit?:number; throughSequence?:number; query?:string; variable?:string; operation?:string; valueType?:string }
const trackingQuery = (query:RunTrackingQuery) => new URLSearchParams(Object.entries(query).filter(([,value])=>value!==undefined).map(([key,value])=>[key,String(value)])).toString()
export const variableTrackingApi = {
  listRun: async (runId:string, query:RunTrackingQuery={}, signal?:AbortSignal) => {
    const result=await apiRequest<components['schemas']['StudioRunVariableTrackingPage']>(`/workflow-runs/${encodeURIComponent(runId)}/variable-tracking?${trackingQuery(query)}`,{signal})
    if(!result.success)return result
    const data=result.data,cursor=query.cursor??0
    if(!data||data.runId!==runId||!Array.isArray(data.tracking)||!Number.isSafeInteger(data.total)||data.total<data.tracking.length
      ||!Number.isSafeInteger(data.throughSequence)||data.throughSequence<0
      ||(query.throughSequence!==undefined&&data.throughSequence!==query.throughSequence)
      ||(data.nextCursor!==null&&data.nextCursor!==cursor+data.tracking.length)
      ||!data.tracking.every((record,index)=>record&&Number.isSafeInteger(record.sequence)&&record.sequence>0&&record.sequence<=data.throughSequence
        &&(index===0||record.sequence>data.tracking[index-1].sequence)&&typeof record.executionId==='string'
        &&['timestamp','variable_name','node_id','node_name','value_type'].every(key=>typeof record[key as keyof RunVariableTrackingRecord]==='string')
        &&['create','update'].includes(record.operation)&&Object.hasOwn(record,'old_value')&&Object.hasOwn(record,'new_value')
        &&record.largeValues&&Object.entries(record.largeValues).every(([key,value])=>['old_value','new_value'].includes(key)&&typeof value==='string')))
      return {success:false,error:'运行变量追踪响应无效，未采用其他运行的数据'}
    return result
  },
  getRunValue: async (runId:string,sequence:number,side:'old_value'|'new_value',signal?:AbortSignal) => {
    const result=await apiRequest<components['schemas']['StudioRunResultValue']>(`/workflow-runs/${encodeURIComponent(runId)}/variable-tracking/values?sequence=${sequence}&side=${side}`,{signal})
    if(!result.success)return result
    if(!result.data||result.data.runId!==runId||result.data.sequence!==sequence||result.data.key!==side||!Object.hasOwn(result.data,'value'))return {success:false,error:'变量完整值响应不属于当前记录'}
    return result
  },
  clearRun: async(runId:string,signal?:AbortSignal)=>{
    const result=await apiRequest<components['schemas']['StudioRunVariableTrackingCleared']>(`/workflow-runs/${encodeURIComponent(runId)}/variable-tracking`,{method:'DELETE',signal})
    if(!result.success)return result
    if(!result.data||result.data.runId!==runId||!result.data.message)return {success:false,error:'服务未确认清空本次运行记录'}
    return result
  },
  exportRun: async(runId:string,throughSequence:number,filters:RunTrackingQuery={},signal?:AbortSignal)=>{
    try{
      const result=await studioFetch(`${getApiBase()}/workflow-runs/${encodeURIComponent(runId)}/variable-tracking/export?${trackingQuery({...filters,throughSequence})}`,{signal})
      if(!result.ok)return {success:false,error:'变量诊断导出失败'}
      return {success:true,data:await result.blob()}
    }catch(error){return {success:false,error:error instanceof Error?error.message:'变量诊断导出失败'}}
  },
  list: async (workflowId: string, signal?: AbortSignal) => {
    const result = await apiRequest<components['schemas']['StudioVariableTrackingResult']>(
      `/workflows/${encodeURIComponent(workflowId)}/variable-tracking`, {signal})
    if (!result.success) return result
    const data = result.data
    if (!data || !Array.isArray(data.tracking) || !Number.isSafeInteger(data.count) || data.count !== data.tracking.length
      || !data.tracking.every(record => record && typeof record === 'object'
        && ['timestamp','variable_name','node_id','node_name','value_type'].every(key => typeof record[key as keyof VariableTrackingRecord] === 'string')
        && ['create','update'].includes(record.operation) && Object.hasOwn(record,'old_value') && Object.hasOwn(record,'new_value'))) {
      return {success:false,error:'变量追踪响应格式错误，保留最后确认记录'}
    }
    return result
  },
  clear: async (workflowId: string, signal?: AbortSignal) => {
    const result = await apiRequest<components['schemas']['StudioVariableTrackingCleared']>(
      `/workflows/${encodeURIComponent(workflowId)}/variable-tracking`, {method:'DELETE',signal})
    if (!result.success) return result
    if (!result.data || typeof result.data.message !== 'string' || !result.data.message.trim()) {
      return {success:false,error:'服务未确认清空变量追踪记录，请刷新确认'}
    }
    return result
  },
}
