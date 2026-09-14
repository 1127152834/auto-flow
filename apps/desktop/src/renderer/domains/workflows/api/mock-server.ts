import {isPathSelectionRequest} from '../lib/pathSelectionContract'
import {isDebugControlRequest,isDebugVariablesRequest} from '../lib/debugControlContract'
import requiredFieldMetadata from '../development/module-required-fields.json'
import {mockBrowserScriptTests,mockScriptTestBusy,invalidateMockScriptTests,configureMockScriptTest} from './mock-browser-script-tests'
import { isSpeechRequest } from '../lib/runSpeech'
import type { components } from '../../../shared/api/generated'
import { mockScheduledRequest, finishScheduledFixture } from './mock-scheduled-tasks'
import { findExcludedModuleType } from '../lib/moduleCatalog'
import { mockSettingsRequest } from './mock-settings'
import { mockAssetRequest } from './mock-assets'
import { mockAssistantRequest } from './mock-assistant'
/** Stateful, browser-local protocol fixture. It never controls a browser or executes user code. */
type Json = null | boolean | number | string | Json[] | { [key: string]: Json }
type ObjectValue = { [key: string]: Json }
interface EventRecord { sequence: number; event: string; data: unknown }
interface SavedFile { folder?: string; filename: string; name: string; modifiedTime: string; size: number; content: ObjectValue }
interface StoredRun {
  runId: string
  workflowId: string
  documentId: string
  workflowName: string
  status: 'starting' | 'running' | 'paused' | 'completed' | 'failed' | 'stopped' | 'interrupted'
  startedAt: string
  finishedAt: string | null
  logCount: number
  requestFingerprint: string
}
interface StoredExecutionLog {
  sequence: number
  id: string
  timestamp: string
  level: 'debug' | 'info' | 'success' | 'warning' | 'error'
  message: string
  nodeId?: string
  duration?: number
  details?: ObjectValue
}
interface Database {
  workflows: Record<string, ObjectValue>
  files: Record<string, SavedFile>
  modules: Record<string, ObjectValue>
  runs: Record<string, StoredRun>
  runLogs: Record<string, StoredExecutionLog[]>
  folder: string
  recordingReviews?: Record<string, ObjectValue>
}
const mockBrowserProfiles: components['schemas']['ProfileRead'][] = [{
  id:'10000000-0000-4000-8000-000000000001',name:'受控浏览器配置（Mock）',description:'仅验证配置选择协议',startUrl:'about:blank',geoip:false,headless:false,humanize:false,humanPreset:'default',browserVersion:'mock',browserEdition:'public',releaseChannel:'stable',proxyMode:'none',fingerprintSeed:1,createdAt:'2026-09-15T00:00:00Z',updatedAt:'2026-09-15T00:00:00Z',
}]
const key = 'autoflow:studio:mock:database:v1'
const empty = (): Database => ({ workflows: {}, files: {}, modules: {}, runs: {}, runLogs: {}, folder: 'mock://AutoFlow/workflows' })
function readDatabase(): Database {
  try { return { ...empty(), ...JSON.parse(localStorage.getItem(key) || '{}') } } catch { return empty() }
}
let db = readDatabase()
const events: EventRecord[] = []
const streams = new Set<ReadableStreamDefaultController<Uint8Array>>()
const encoder = new TextEncoder()
let offline = false
let failNextSave = false
let failNextRun = false
let failNextPickerStop = false
let selectorTest: 'none' | 'single' | 'multiple' | 'error' = 'single'
let nextExecutionOrder: string[] | null = null
const runRows = new Map<string, ObjectValue[]>()
const tracking = new Map<string, ObjectValue[]>()
let lastVariables: ObjectValue = {}
const clientSettings = { verboseLog: true, workflowId: 'current' }
let failNextRequiredFields = false
let browser = false
let url = 'about:blank'
let browserSessionId = ''
let browserPageRevision = 0
let targetPageId: string | null = null
let browserPages: components['schemas']['StudioBrowserPage'][] = []
const browserPageState = () => ({sessionId:browserSessionId,revision:browserPageRevision,targetPageId,pages:browserPages})
/** Test-service event fixture, not an automation executor. */
export function configureMockBrowserPages(pages:components['schemas']['StudioBrowserPage'][], target:string|null=targetPageId) {
  browserPages=pages;targetPageId=pages.some(page=>page.pageId===target)?target:null;browserPageRevision++
  closePickerSession();invalidateMockScriptTests(false)
}

let recording = false
let recorded: ObjectValue[] = []
let recordingSessionId: string | null = null
const retiredRecordings = new Set<string>()
let picking = false
let pickerSessionId: string | null = null
let pickerRequestFingerprint: string | null = null
const retiredPickerSessions = new Set<string>()
let picked: ObjectValue | null = null
let similarPicked: ObjectValue | null = null
const speechRequests = new Map<string, components['schemas']['StudioSpeechState']>()
const jsRequests = new Map<string, components['schemas']['StudioJsScriptState']>()
let run: { pauseId:string|null; controlRevision:number; tts?: {requestId:string;nodeId:string}; js?: { requestId: string; nodeId: string; resultVariable: string }; id: string; runId: string; documentId: string; nodes: ObjectValue[]; index: number; paused: boolean; step: boolean; breakpoints: string[]; nodeIds: string[]; variables: ObjectValue; input?: { requestId: string; nodeId: string; variableName: string; mode: string }; timer?: ReturnType<typeof setTimeout> } | null = null
const inputRequests = new Map<string, { requestId: string; workflowId: string; nodeId: string; status: 'pending' | 'answered' | 'cancelled' | 'expired' }>()
type CommandRecord = { fingerprint:string; response:ObjectValue; status:number }
const commandResults = new Map<string, CommandRecord>()
const pendingCommands = new Map<string,{fingerprint:string;result:Promise<CommandRecord>}>()
const response = (data: unknown, status = 200) => Response.json(data, { status })
const failure = (message: string, status = 400) => response({ success: false, error: message, detail: message }, status)
async function applyIdentifiedCommand(id:string,fingerprint:string,apply:()=>Response):Promise<Response> {
  const previous=commandResults.get(id)
  if(previous)return previous.fingerprint===fingerprint?response(previous.response,previous.status):failure('命令 ID 冲突',409)
  const pending=pendingCommands.get(id)
  if(pending){
    if(pending.fingerprint!==fingerprint)return failure('命令 ID 冲突',409)
    const result=await pending.result
    return response(result.response,result.status)
  }
  const result=(async()=>{
    let outcome:Response
    try{outcome=apply()}catch(error){outcome=failure(error instanceof Error?error.message:'命令处理失败',500)}
    const record={fingerprint,response:{...await outcome.json(),commandId:id},status:outcome.status}
    commandResults.set(id,record)
    return record
  })()
  pendingCommands.set(id,{fingerprint,result})
  try{const record=await result;return response(record.response,record.status)}
  finally{pendingCommands.delete(id)}
}
const encode = (e: EventRecord) => encoder.encode(`id: ${e.sequence}\nevent: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`)
export function emitMockEvent(event: string, data: unknown) {
  const e = { sequence: events.length + 1, event, data }
  events.push(e)
  for (const stream of streams) stream.enqueue(encode(e))
}
function persist(next: Database) { localStorage.setItem(key, JSON.stringify(next)); db = next }
function emitRunLog(current: NonNullable<typeof run>, log: Omit<StoredExecutionLog, 'sequence'> & { isUserLog?: boolean; isSystemLog?: boolean }) {
  const previous = db.runLogs[current.runId] || []
  const entry: StoredExecutionLog = {
    sequence: previous.length + 1,
    id: log.id,
    timestamp: log.timestamp,
    level: log.level,
    message: log.message,
    ...(log.nodeId ? { nodeId: log.nodeId } : {}),
    ...(log.duration !== undefined ? { duration: log.duration } : {}),
    ...(log.details ? { details: log.details } : {}),
  }
  const runRecord = db.runs[current.runId]
  persist({
    ...db,
    runLogs: { ...db.runLogs, [current.runId]: [...previous, entry] },
    runs: runRecord ? { ...db.runs, [current.runId]: { ...runRecord, logCount: entry.sequence } } : db.runs,
  })
  emitMockEvent('execution:log', { workflowId: current.id, runId: current.runId, log })
}
export function configureMock(options: { failNextRequiredFields?: boolean; scriptTest?: {result?:unknown;error?:string;hold?:boolean}; offline?: boolean; failNextSave?: boolean; failNextRun?: boolean; failNextPickerStop?: boolean; disconnect?: boolean; executionOrder?: string[] | null; selectorTest?: typeof selectorTest }) {
  if (options.failNextRequiredFields !== undefined) failNextRequiredFields = options.failNextRequiredFields
  if (options.scriptTest !== undefined) configureMockScriptTest(options.scriptTest)
  if (options.selectorTest !== undefined) selectorTest = options.selectorTest
  if (options.executionOrder !== undefined) nextExecutionOrder = options.executionOrder === null ? null : [...options.executionOrder]
  if (options.offline !== undefined) offline = options.offline
  if (options.failNextPickerStop !== undefined) failNextPickerStop = options.failNextPickerStop
  if (options.failNextRun !== undefined) failNextRun = options.failNextRun
  if (options.failNextSave !== undefined) failNextSave = options.failNextSave
  if (options.disconnect || options.offline) {
    for (const stream of streams) stream.close()
    streams.clear()
  }
}
export function mockSnapshot() { return { offline, browser, recording, picking, pickerSessionId, url, run: run?.id ?? null, pause:run?.paused&&run.pauseId?{runId:run.runId,pauseId:run.pauseId,controlRevision:run.controlRevision}:null, sequence: events.length } }
export function seedMockRunHistory(options: { runId: string; workflowId: string; documentId: string; workflowName?: string; logs: Array<Omit<StoredExecutionLog, 'sequence'>> }) {
  const startedAt = new Date().toISOString()
  const logs = options.logs.map((log, index) => ({ ...structuredClone(log), sequence: index + 1 }))
  persist({
    ...db,
    runs: { ...db.runs, [options.runId]: {
      runId: options.runId, workflowId: options.workflowId, documentId: options.documentId,
      workflowName: options.workflowName || 'Mock 运行', status: 'completed', startedAt,
      finishedAt: startedAt, logCount: logs.length, requestFingerprint: `seed:${options.runId}`,
    } },
    runLogs: { ...db.runLogs, [options.runId]: logs },
  })
}
export function addMockRecordingEvent(event: ObjectValue) {
  if (!recording) throw new Error('请先在录制面板开始录制')
  recorded.push({ ...event, ts: Date.now(), sequence: recorded.length + 1 })
}
export function selectMockElement(selector: string) {
  if (!picking) throw new Error('请先开启元素拾取')
  similarPicked = null
  picked = { selector, tag: 'button', tagName:'BUTTON', attributes:{id:selector.replace(/^#/, '')}, text: 'Mock 目标', hints: { selectors: [selector] } }
}
export function selectMockSimilarElements() {
  if (!picking) throw new Error('请先开启元素拾取')
  picked = null
  similarPicked = { pattern: '.item:nth-child({index})', count: 4, indices: [1, 2, 3, 4], minIndex: 1, maxIndex: 4, selector1: '.item:nth-child(1)', selector2: '.item:nth-child(2)' }
}
function closePickerSession() {
  const closedSessionId = pickerSessionId
  if (closedSessionId) retiredPickerSessions.add(closedSessionId)
  picking = false
  pickerSessionId = null
  pickerRequestFingerprint = null
  picked = null
  similarPicked = null
  return closedSessionId
}
function pickerSessionFrom(target: URL, body: ObjectValue, method: string) {
  const value = method === 'GET' ? target.searchParams.get('sessionId') : body.sessionId
  return typeof value === 'string' && value.trim() ? value : null
}
function pickerState(sessionId: string, active: boolean) {
  return { success: true, sessionId, active, selected: active ? picked !== null || similarPicked !== null : false }
}
const finishedWorkflows = new Set<string>()
function finish(status: string) {
  if (!run) return
  clearTimeout(run.timer)
  if (run.input) { const request = inputRequests.get(run.input.requestId); if (request) request.status = 'expired' }
  if (run.js) { const request = jsRequests.get(run.js.requestId); if (request && ['pending', 'claimed'].includes(request.status)) request.status = 'expired' }
  if (run.tts) { const request = speechRequests.get(run.tts.requestId); if (request && ['pending','claimed'].includes(request.status)) request.status = 'expired' }
  const terminalStatus = status === 'completed' ? 'completed' : status === 'failed' ? 'failed' : 'stopped'
  const record = db.runs[run.runId]
  if (record) persist({ ...db, runs: { ...db.runs, [run.runId]: { ...record, status: terminalStatus, finishedAt: new Date().toISOString() } } })
  emitMockEvent('execution:completed', { workflowId: run.id, runId: run.runId, result: { status, executedNodes: run.index, failedNodes: status === 'failed' ? 1 : 0 } })
  finishScheduledFixture(run.id, status, run.index)
  lastVariables = structuredClone(run.variables)
  finishedWorkflows.add(run.id)
  run = null
}
function stopRun(id: unknown): Response {
  if (typeof id !== 'string' || !id.trim()) return failure('缺少目标工作流标识', 400)
  if (run?.id === id) { finish('stopped'); return response({ success: true }) }
  if (finishedWorkflows.has(id)) return response({ success: true })
  return failure(run ? '停止请求不属于当前运行' : '目标工作流没有活跃运行', 409)
}
function writeRunVariable(name: string, value: Json, nodeId: string, nodeName: string) {
  if (!run) return
  const existed = Object.hasOwn(run.variables, name)
  const old = run.variables[name]
  if (existed && JSON.stringify(old) === JSON.stringify(value)) return
  Object.defineProperty(run.variables, name, { value: structuredClone(value), enumerable: true, configurable: true, writable: true })
  tracking.get(run.id)?.push({timestamp:new Date().toISOString(),variable_name:name,old_value:existed ? structuredClone(old) : null,new_value:structuredClone(value),node_id:nodeId,node_name:nodeName,operation:existed?'update':'create',value_type:value===null?'null':Array.isArray(value)?'array':typeof value})
}
function currentVariableMeta(current:NonNullable<typeof run>):ObjectValue {
  const records=tracking.get(current.id)||[]
  return Object.fromEntries(Object.keys(current.variables).map(name=>{
    const source=[...records].reverse().find(record=>record.variable_name===name)?.node_name
    return [name,{scope:'workflow',readOnly:false,source:typeof source==='string'?source:'流程初值'}]
  }))
}
function submitInput(data: Json | undefined): Response {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return failure('缺少输入请求信息', 422)
  const pending = run?.input
  if (!run || !pending || data.requestId !== pending.requestId) return failure('输入请求不存在或已结束', 409)
  if (data.value !== null && typeof data.value !== 'string') return failure('输入结果必须是字符串或 null', 422)
  let value: Json = data.value
  if (value !== null) {
    if (['number', 'integer', 'slider_int', 'slider_float'].includes(pending.mode)) {
      const numeric = Number(value)
      if (!value.trim() || !Number.isFinite(numeric) || (['integer', 'slider_int'].includes(pending.mode) && !Number.isInteger(numeric))) return failure('输入结果不是有效数值', 422)
      value = numeric
    } else if (pending.mode === 'checkbox') {
      if (!['true', 'false'].includes(value)) return failure('输入结果不是有效布尔值', 422)
      value = value === 'true'
    } else if (pending.mode === 'list') value = value.split('\n').map(line => line.trim()).filter(Boolean)
    else if (pending.mode === 'select_multiple') {
      try { value = JSON.parse(value) as Json } catch { return failure('多选结果不是 JSON 数组', 422) }
      if (!Array.isArray(value) || value.some(item => typeof item !== 'string')) return failure('多选结果不是字符串数组', 422)
    }
    writeRunVariable(pending.variableName, value, pending.nodeId, '[Mock] 输入结果')
  }
  // Consume the pending identity before scheduling: another command cannot answer it again.
  const request = inputRequests.get(pending.requestId)
  if (request) request.status = value === null ? 'cancelled' : 'answered'
  run.input = undefined
  emitRunLog(run, {id: crypto.randomUUID(),timestamp:new Date().toISOString(),nodeId:pending.nodeId,level:'info',message:value === null ? '[Mock] 用户取消输入，变量保持不变' : '[Mock] 已接收输入结果',isSystemLog:true})
  emitMockEvent('execution:node_complete', {workflowId:run.id,runId:run.runId,nodeId:pending.nodeId,success:true})
  run.index++
  tick()
  return response({success:true,requestId:pending.requestId,mock:true})
}
function submitJs(event: string, data: Json | undefined): Response {
  if (!data || typeof data !== 'object' || Array.isArray(data)
    || typeof data.requestId !== 'string' || typeof data.claimId !== 'string' || !data.claimId.trim()) return failure('脚本请求及领取标识无效', 422)
  const pending = run?.js
  const state = jsRequests.get(data.requestId)
  if (!run || !pending || pending.requestId !== data.requestId || !state) return failure('脚本请求不存在或已结束', 409)
  if (event === 'js_script_claim') {
    if (state.status === 'claimed' && state.claimId === data.claimId) return response({success:true,requestId:data.requestId})
    if (state.status !== 'pending') return failure('脚本已由其它客户端领取', 409)
    state.status = 'claimed'; state.claimId = data.claimId
    return response({success:true,requestId:data.requestId})
  }
  if (state.status !== 'claimed' || state.claimId !== data.claimId) return failure('脚本结果不属于当前领取者', 409)
  if (typeof data.success !== 'boolean' || (data.success && (!data.variables || typeof data.variables !== 'object' || Array.isArray(data.variables)))
    || (!data.success && (typeof data.error !== 'string' || !data.error.trim()))) return failure('脚本结果格式无效', 422)
  clearTimeout(run.timer)
  state.status = data.success ? 'completed' : 'failed'
  emitMockEvent('execution:node_complete', {workflowId:run.id,runId:run.runId,nodeId:pending.nodeId,success:data.success})
  if (!data.success) {
    emitRunLog(run, {id:crypto.randomUUID(),timestamp:new Date().toISOString(),nodeId:pending.nodeId,level:'error',message:`[Mock] 前端脚本失败: ${data.error}`,isSystemLog:true})
    finish('failed'); return response({success:true,requestId:data.requestId})
  }
  const variables = data.variables as ObjectValue
  for (const name of Object.keys(run.variables)) if (Object.hasOwn(variables,name)) writeRunVariable(name, variables[name], pending.nodeId, '[Mock] 前端脚本变量')
  if (pending.resultVariable) writeRunVariable(pending.resultVariable, data.result ?? null, pending.nodeId, '[Mock] 前端脚本返回值')
  emitRunLog(run, {id:crypto.randomUUID(),timestamp:new Date().toISOString(),nodeId:pending.nodeId,level:'info',message:'[Mock] 已确认前端脚本结果；未执行网页动作',isSystemLog:true})
  run.js = undefined; run.index++; tick()
  return response({success:true,requestId:data.requestId})
}
function submitSpeech(event: string, data: Json | undefined): Response {
  if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.requestId !== 'string'
    || typeof data.claimId !== 'string' || !data.claimId.trim()) return failure('语音请求及领取标识无效',422)
  const pending = run?.tts
  const state = speechRequests.get(data.requestId)
  if (!run || !pending || pending.requestId !== data.requestId || !state) return failure('语音请求不存在或已结束',409)
  if (event === 'tts_claim') {
    if (state.status === 'claimed' && state.claimId === data.claimId) return response({success:true,requestId:data.requestId})
    if (state.status !== 'pending') return failure('语音已由其它客户端领取',409)
    state.status = 'claimed'; state.claimId = data.claimId
    return response({success:true,requestId:data.requestId})
  }
  if (state.status !== 'claimed' || state.claimId !== data.claimId) return failure('语音结果不属于当前领取者',409)
  if (typeof data.success !== 'boolean' || (!data.success && (typeof data.error !== 'string' || !data.error.trim()))) return failure('语音结果格式无效',422)
  clearTimeout(run.timer)
  state.status = data.success ? 'completed' : 'failed'
  emitMockEvent('execution:node_complete',{workflowId:run.id,runId:run.runId,nodeId:pending.nodeId,success:data.success})
  emitRunLog(run, {id:crypto.randomUUID(),timestamp:new Date().toISOString(),nodeId:pending.nodeId,level:data.success?'info':'error',message:data.success?'[Mock] 已确认前端语音结果；未执行网页动作':`[Mock] 语音失败: ${data.error}`,isSystemLog:true})
  if (data.success) { run.tts = undefined; run.index++; tick() }
  else finish('failed')
  return response({success:true,requestId:data.requestId})
}
function applyCommand(event: string, data: Json | undefined): Response {
  if (event === 'tts_claim' || event === 'tts_result') return submitSpeech(event,data)
  if (event === 'js_script_claim' || event === 'js_script_result') return submitJs(event, data)
  if (event === 'input_prompt_result') return submitInput(data)
  const payload = data && typeof data === 'object' && !Array.isArray(data) ? data : {}
  if (event === 'execution_stop') return stopRun(payload.workflowId)
  if (event === 'set_verbose_log') {
    if (typeof payload.enabled !== 'boolean') return failure('enabled 必须为布尔值', 422)
    clientSettings.verboseLog = payload.enabled
    return response({ success: true, enabled: clientSettings.verboseLog, mock: true })
  }
  if (event === 'set_current_workflow') {
    if (typeof payload.workflowId !== 'string' || !payload.workflowId.trim()) return failure('workflowId 必须为非空字符串', 422)
    clientSettings.workflowId = payload.workflowId
    return response({ success: true, workflowId: clientSettings.workflowId, mock: true })
  }
  return failure(`Mock 尚未实现命令：${event}`, 501)
}
function tick(skipBreakpoint = false) {
  if (!run) return
  const current = run
  if (current.index >= current.nodes.length) { finish('completed'); return }
  const node = current.nodes[current.index]
  const nodeId = String(node.id)
  const data = node.data as ObjectValue | undefined
  if (!skipBreakpoint && (current.step || current.breakpoints.includes(nodeId))) {
    current.paused = true
    current.pauseId = crypto.randomUUID()
    current.controlRevision++
    emitMockEvent('execution:paused', { workflowId: current.id, runId:current.runId, pauseId:current.pauseId, controlRevision:current.controlRevision, node_id: nodeId, label: data?.label ?? node.type, variables: current.variables, variableMeta:currentVariableMeta(current), reason: current.step ? 'step' : 'breakpoint' })
    return
  }
  current.paused = false
  emitMockEvent('execution:node_start', { workflowId: current.id, runId:current.runId, nodeId })
  current.timer = setTimeout(() => {
    if (run !== current) return
    if (String(node.type) === 'js_script') {
      const code = typeof data?.code === 'string' ? data.code : ''
      if (!code.trim()) { finish('failed'); return }
      const requestId = crypto.randomUUID()
      current.js = {requestId,nodeId,resultVariable:typeof data?.resultVariable === 'string' ? data.resultVariable.trim() : ''}
      jsRequests.set(requestId,{requestId,workflowId:current.id,nodeId,status:'pending',claimId:null})
      emitMockEvent('execution:js_script',{requestId,workflowId:current.id,nodeId,code,variables:structuredClone(current.variables)})
      current.timer = setTimeout(() => {
        if (run !== current || current.js?.requestId !== requestId) return
        emitRunLog(current, {id:crypto.randomUUID(),timestamp:new Date().toISOString(),nodeId,level:'error',message:'[Mock] 等待前端脚本结果超过30秒',isSystemLog:true})
        emitMockEvent('execution:node_complete',{workflowId:current.id,runId:current.runId,nodeId,success:false})
        finish('failed')
      }, 30000)
      return
    }
    if (String(node.type) === 'text_to_speech') {
      const requestId = crypto.randomUUID()
      const payload = {requestId,workflowId:current.id,nodeId,text:data?.text??'',lang:data?.lang??'zh-CN',rate:data?.rate??1,pitch:data?.pitch??1,volume:data?.volume??1}
      if (!isSpeechRequest(payload)) {
        emitMockEvent('execution:node_complete',{workflowId:current.id,runId:current.runId,nodeId,success:false})
        emitRunLog(current, {id:crypto.randomUUID(),timestamp:new Date().toISOString(),nodeId,level:'error',message:'[Mock] 语音参数无效，未发起朗读',isSystemLog:true})
        finish('failed'); return
      }
      current.tts = {requestId,nodeId}
      speechRequests.set(requestId,{requestId,workflowId:current.id,nodeId,status:'pending',claimId:null})
      emitMockEvent('execution:tts_request',payload)
      current.timer = setTimeout(() => {
        if (run !== current || current.tts?.requestId !== requestId) return
        emitMockEvent('execution:node_complete',{workflowId:current.id,runId:current.runId,nodeId,success:false})
        emitRunLog(current, {id:crypto.randomUUID(),timestamp:new Date().toISOString(),nodeId,level:'error',message:'[Mock] 等待语音结果超过60秒',isSystemLog:true})
        finish('failed')
      },60000)
      return
    }
    if (String(node.type) === 'input_prompt') {
      const variableName = typeof data?.variableName === 'string' ? data.variableName.trim() : ''
      if (!variableName) {
        emitMockEvent('execution:node_complete', {workflowId:current.id,runId:current.runId,nodeId,success:false})
        finish('failed'); return
      }
      const mode = typeof data?.inputMode === 'string' ? data.inputMode : 'single'
      const requestId = crypto.randomUUID()
      current.input = {requestId,nodeId,variableName,mode}
      inputRequests.set(requestId, {requestId, workflowId:current.id, nodeId, status:'pending'})
      const configuredOptions = data?.selectOptions
      const options = Array.isArray(configuredOptions) ? configuredOptions : typeof configuredOptions === 'string' ? current.variables[configuredOptions.replace(/^\{(.*)\}$/, '$1')] : []
      emitMockEvent('execution:input_prompt', {
        requestId,workflowId:current.id,nodeId,variableName,inputMode:mode,
        title:data?.promptTitle || '输入',message:data?.promptMessage || '请输入值:',defaultValue:data?.defaultValue ?? '',
        minValue:data?.minValue,maxValue:data?.maxValue,maxLength:data?.maxLength,required:data?.required !== false,
        selectOptions:Array.isArray(options)?options.map(item=>typeof item==='string'?item:JSON.stringify(item)):[],
      })
      return
    }
    emitRunLog(current, { id: crypto.randomUUID(), timestamp: new Date().toISOString(), level: 'info', nodeId, message: `[Mock] 第 ${current.index + 1} 次调度：已模拟 ${data?.label ?? node.type} 的事件；未执行网页动作`, duration: 300, isSystemLog: true })
    if (failNextRun) {
      failNextRun = false
      emitRunLog(current, { id: crypto.randomUUID(), timestamp:new Date().toISOString(),nodeId,level:'error',message:'[Mock] Simulated node failure',isSystemLog:true })
      emitMockEvent('execution:node_complete', {workflowId:current.id,runId:current.runId,nodeId,success:false})
      finish('failed');return
    }
    emitMockEvent('execution:node_complete', {workflowId:current.id,runId:current.runId,nodeId,success:true})
    if (String(node.type) === 'get_element_info' || String(node.type) === 'extract_table_data') {
      const row = { mock:true, nodeId, value:'Mock result', index:current.index+1 }
      runRows.get(current.id)?.push(row)
      emitMockEvent('execution:data_row', {workflowId:current.id,runId:current.runId,row})
    }
    current.index++
    tick()
  }, 300)
}
function streamResponse(after: number, signal?: AbortSignal | null) {
  let controller: ReadableStreamDefaultController<Uint8Array>
  const close = () => { if (streams.delete(controller)) controller.close() }
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c
      for (const e of events) if (e.sequence > after) c.enqueue(encode(e))
      streams.add(c)
      signal?.addEventListener('abort', close, { once: true })
      if (signal?.aborted) close()
    },
    cancel() { streams.delete(controller); signal?.removeEventListener('abort', close) },
  })
  return new Response(body, { headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' } })
}
function validBreakpoints(value: unknown, nodeIds: string[]): value is string[] {
  return Array.isArray(value) && value.every(id => typeof id === 'string' && nodeIds.includes(id))
}
function startRun(id: string, doc: ObjectValue | undefined, body: ObjectValue): Response {
        if (!doc) return failure('工作流不存在', 404)
        if (body.runId !== undefined && (typeof body.runId !== 'string' || !body.runId.trim())) return failure('运行 ID 无效', 422)
        const requestedRunId = typeof body.runId === 'string' ? body.runId.trim() : ''
        const runId = requestedRunId || crypto.randomUUID()
        const documentId = typeof body.documentId === 'string' && body.documentId.trim() ? body.documentId.trim() : id
        const requestFingerprint = JSON.stringify({ workflowId: id, documentId, body })
        const previous = db.runs[runId]
        if (previous) {
          if (previous.requestFingerprint !== requestFingerprint) return failure('运行 ID 冲突', 409)
          return response({ success: true, workflowId: id, runId, status: previous.status, mock: true })
        }
        if (run || recording || picking || mockScriptTestBusy()) return failure('Mock 浏览器正被运行、录制或拾取占用', 409)
        // Protocol fixture deliberately visits source order; it is not a replacement execution engine.
        const sourceNodes = structuredClone(doc.nodes) as ObjectValue[]
        let nodes = sourceNodes
        const nodeIds = sourceNodes.map(node => String(node.id))
        const breakpoints = body.breakpoints === undefined ? [] : body.breakpoints
        if (!validBreakpoints(breakpoints, nodeIds)) return failure('断点必须是运行快照中的节点标识数组', 422)
        if (findExcludedModuleType(nodes, moduleId => {
          const children = (db.modules[moduleId]?.workflow as ObjectValue | undefined)?.nodes
          return Array.isArray(children) ? children : undefined
        })) return failure('工作流包含已排除节点', 422)
        if (nextExecutionOrder !== null) {
          const byId = new Map(sourceNodes.map(node => [String(node.id), node]))
          if (nextExecutionOrder.some(nodeId => typeof nodeId !== 'string' || !byId.has(nodeId))) return failure('Mock 轨迹包含快照中不存在的节点', 422)
          // Explicit fixture order tests branches/repeated events; it never evaluates conditions or user code.
          nodes = nextExecutionOrder.map(nodeId => byId.get(nodeId)!)
        }
        const index = body.startNodeId ? nodes.findIndex(n => n.id === body.startNodeId) : 0
        if (index < 0) return failure('起点不存在')
        nextExecutionOrder = null
        finishedWorkflows.delete(id)
        runRows.set(id, [])
        const startedAt = new Date().toISOString()
        persist({ ...db,
          runs: { ...db.runs, [runId]: { runId, workflowId: id, documentId, workflowName: String(doc.name || '未命名工作流'), status: 'starting', startedAt, finishedAt: null, logCount: 0, requestFingerprint } },
          runLogs: { ...db.runLogs, [runId]: [] },
        })
        run = { id, runId, documentId, nodes, index, pauseId:null, controlRevision:0, paused: false, step: body.stepMode === true, breakpoints: [...breakpoints], nodeIds, variables: Object.fromEntries(((doc.variables || []) as ObjectValue[]).filter(v => Object.hasOwn(v, 'value')).map(v => [String(v.name), v.value])) }
        tracking.set(id,Object.entries(run.variables).map(([name,value])=>({timestamp:new Date().toISOString(),variable_name:name,old_value:null,new_value:value,node_id:'',node_name:'[Mock] Initial values',operation:'create',value_type:typeof value})))
        run.timer = setTimeout(() => {
          if (run?.id !== id || run.runId !== runId) return
          const record = db.runs[runId]
          if (record) persist({ ...db, runs: { ...db.runs, [runId]: { ...record, status: 'running' } } })
          emitMockEvent('execution:started', { workflowId: id, runId })
          tick()
        }, 30)
        return response({ success: true, workflowId: id, runId, status: 'starting', mock: true })
}
export async function mockRequest(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const signal = init.signal ?? (input instanceof Request ? input.signal : undefined)
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
  if (offline) throw new TypeError('Mock network offline')
  const target = new URL(input instanceof Request ? input.url : String(input), 'http://autoflow-studio.mock')
  if (target.hostname !== 'autoflow-studio.mock') return failure('Mock 模式禁止访问外部服务', 403)
  const path = decodeURIComponent(target.pathname.replace(/^\/api/, ''))
  const method = init.method ?? (input instanceof Request ? input.method : 'GET')
  let body: ObjectValue = {}
  let form: FormData | undefined
  try {
    const raw = init.body ?? (input instanceof Request && input.body ? new Uint8Array(await input.clone().arrayBuffer()) : undefined)
    const headers = new Headers(init.headers ?? (input instanceof Request ? input.headers : undefined))
    if (raw instanceof FormData) form = raw
    else if (headers.get('content-type')?.includes('multipart/form-data')) {
      form = await new Response(raw, { headers }).formData()
    } else if ((typeof raw === 'string' && raw) || raw instanceof Uint8Array) {
      const parsed: unknown = JSON.parse(typeof raw === 'string' ? raw : new TextDecoder().decode(raw))
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return failure('请求不是合法 JSON 对象')
      body = parsed as ObjectValue
    }
  } catch { return failure('请求不是合法 JSON 或 multipart 数据') }
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
  try {
    const assetResult = await mockAssetRequest(path, method, target.searchParams, body, form)
    if (assetResult) return assetResult
    const settingsResult = mockSettingsRequest(path, method, body)
    if (settingsResult) return settingsResult
    const assistantResult = await mockAssistantRequest(path,method,body,signal,emitMockEvent)
    if (assistantResult) return assistantResult
    // Another preview/renderer may have saved since this module was loaded.
    db = readDatabase()
    const scheduledResult = await mockScheduledRequest(path, method, target.searchParams, body, {
      start: async task => {
        const file = Object.values(db.files).find(file => file.filename === task.workflow_id && (file.folder || db.folder) === db.folder)
        return startRun(`scheduled-${task.id}`, file?.content, {})
      },
      stop: async task => {
        if (run?.id !== `scheduled-${task.id}`) return failure('Task is not running', 409)
        finish('stopped'); return response({ success: true })
      },
    })
    if (scheduledResult) return scheduledResult
    if (path === '/events/stream') {
      const after = Number(target.searchParams.get('afterSeq') || 0)
      if (!Number.isSafeInteger(after) || after < 0) return failure('Invalid event cursor', 400)
      if (after > events.length) return failure('Event cursor exceeds the current journal', 409)
      return streamResponse(after, signal)
    }
    const speechQuery = path.match(/^\/events\/tts-requests\/([^/]+)$/)
    if (speechQuery) {
      if (method !== 'GET') return failure('语音状态查询只接受 GET',405)
      const state = speechRequests.get(decodeURIComponent(speechQuery[1]))
      return state ? response(state) : failure('语音请求不存在',404)
    }
    const jsQuery = path.match(/^\/events\/js-requests\/([^/]+)$/)
    if (jsQuery) {
      if (method !== 'GET') return failure('脚本状态查询只接受 GET', 405)
      const state = jsRequests.get(decodeURIComponent(jsQuery[1]))
      return state ? response(state) : failure('脚本请求不存在', 404)
    }
    const inputQuery = path.match(/^\/events\/input-prompts\/([^/]+)$/)
    if (inputQuery) {
      if (method !== 'GET') return failure('输入状态查询只接受 GET 请求', 405)
      const request = inputRequests.get(decodeURIComponent(inputQuery[1]))
      return request ? response(request) : failure('输入请求不存在', 404)
    }
    const commandQuery = path.match(/^\/events\/commands\/([^/]+)$/)
    if (commandQuery && method === 'GET') {
      const commandId=decodeURIComponent(commandQuery[1])
      const pending=pendingCommands.get(commandId)
      const previous = pending?await pending.result:commandResults.get(commandId)
      return previous ? response({ ...previous.response, httpStatus: previous.status }) : failure('命令不存在', 404)
    }
    if (path === '/events/commands') {
      if (method !== 'POST') return failure('命令提交只接受 POST 请求', 405)
      if (typeof body.commandId !== 'string' || !body.commandId.trim() || typeof body.event !== 'string' || !body.event.trim()) return failure('缺少命令标识或事件名', 400)
      const id = body.commandId
      const fingerprint = JSON.stringify(body)
      return applyIdentifiedCommand(id,fingerprint,()=>applyCommand(body.event as string,body.data))
    }
    if (path === '/local-workflows/default-folder' || path === '/local-workflows/active-folder') {
      if (method === 'POST') persist({ ...db, folder: String(body.folder || empty().folder) })
      return response({ success: true, folder: db.folder || empty().folder, default: 'mock://AutoFlow/workflows' })
    }
    const folder = String(body.folder || (body.content as ObjectValue | undefined)?._folder || target.searchParams.get('folder') || db.folder || empty().folder)
    const fileKey = (filename: string) => `${folder}/${filename}`
    const findFile = (filename: string) => db.files[fileKey(filename)] || (folder === (db.folder || empty().folder) ? db.files[filename] : undefined)
    if (path === '/local-workflows/open-folder') return response({success:true, folder, mock:true})
    if (path === '/local-workflows/list') return response({ workflows: Object.values(db.files).filter(file => (file.folder || db.folder || empty().folder) === folder).map(({ content: _content, ...file }) => file).sort((a,b) => b.modifiedTime.localeCompare(a.modifiedTime)) })
    if (path === '/local-workflows/check-exists') {
      const filename = `${String(body.filename).replace(/\.json$/, '')}.json`
      return response({ exists: !!findFile(filename), filename })
    }
    if (path === '/local-workflows/save-to-folder' || path === '/local-workflows/import') {
      if (failNextSave) { failNextSave = false; return failure('Mock：磁盘写入失败，草稿未保存', 507) }
      let content = body.content as ObjectValue
      if (!content || !Array.isArray(content.nodes)) return failure('工作流缺少 nodes')
      const filename = `${String(body.filename ?? content.name ?? '未命名流程').replace(/\.json$/, '')}.json`
      if (content.selfHeal === undefined && findFile(filename)?.content.selfHeal !== undefined) content = { ...content, selfHeal: findFile(filename)!.content.selfHeal }
      const file = { folder, filename, name: String(content.name || filename), modifiedTime: new Date().toISOString(), size: new Blob([JSON.stringify(content)]).size, content }
      persist({ ...db, files: { ...db.files, [fileKey(filename)]: file } })
      return response({ success: true, filename })
    }
    if (path.startsWith('/local-workflows/load/')) {
      const file = findFile(path.slice('/local-workflows/load/'.length))
      return file ? response({ success: true, content: file.content }) : failure('工作流不存在', 404)
    }
    if (path === '/local-workflows/delete') {
      const files = { ...db.files }; const filename = target.searchParams.get('filename') || ''; delete files[fileKey(filename)]; if (folder === (db.folder || empty().folder)) delete files[filename]
      persist({ ...db, files }); return response({ success: true })
    }
    if (path === '/workflow-runs') {
      if (method !== 'GET') return failure('运行历史只接受 GET 请求', 405)
      const cursor = Number(target.searchParams.get('cursor') || 0)
      const limit = Number(target.searchParams.get('limit') || 20)
      if (!Number.isSafeInteger(cursor) || cursor < 0 || !Number.isSafeInteger(limit) || limit < 1 || limit > 500) return failure('运行历史分页参数无效', 422)
      const documentId = target.searchParams.get('documentId')?.trim()
      const rows = Object.values(db.runs)
        .filter(item => !documentId || item.documentId === documentId)
        .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
      const items = rows.slice(cursor, cursor + limit).map(({ requestFingerprint: _fingerprint, ...item }) => item)
      return response({ items, total: rows.length, nextCursor: cursor + items.length < rows.length ? cursor + items.length : null })
    }
    const executionLogs = path.match(/^\/workflow-runs\/([^/]+)\/logs(\/export)?$/)
    if (executionLogs) {
      if (method !== 'GET') return failure('运行日志只接受 GET 请求', 405)
      const runId = decodeURIComponent(executionLogs[1])
      const record = db.runs[runId]
      if (!record) return failure('运行记录不存在', 404)
      const allowedLevels = new Set(['debug', 'info', 'success', 'warning', 'error'])
      const rawLevels = target.searchParams.get('levels')
      const levels = rawLevels ? rawLevels.split(',').filter(Boolean) : []
      if (levels.some(level => !allowedLevels.has(level))) return failure('日志级别筛选无效', 422)
      const query = (target.searchParams.get('query') || '').trim().toLocaleLowerCase('zh-CN')
      const nodeId = (target.searchParams.get('nodeId') || '').trim()
      const filtered = (db.runLogs[runId] || []).filter(log =>
        (!levels.length || levels.includes(log.level))
        && (!query || log.message.toLocaleLowerCase('zh-CN').includes(query))
        && (!nodeId || log.nodeId === nodeId)
      )
      if (executionLogs[2]) {
        const body = filtered.map(log => JSON.stringify({ runId, workflowId: record.workflowId, ...log })).join('\n') + (filtered.length ? '\n' : '')
        return new Response(body, { headers: { 'Content-Type': 'application/x-ndjson; charset=utf-8', 'Content-Disposition': `attachment; filename="workflow-logs-${runId}.jsonl"` } })
      }
      const cursor = Number(target.searchParams.get('cursor') || 0)
      const limit = Number(target.searchParams.get('limit') || 100)
      if (!Number.isSafeInteger(cursor) || cursor < 0 || !Number.isSafeInteger(limit) || limit < 1 || limit > 500) return failure('日志分页参数无效', 422)
      const end = Math.max(0, filtered.length - cursor)
      const start = Math.max(0, end - limit)
      const items = filtered.slice(start, end)
      return response({ runId, workflowId: record.workflowId, items, total: filtered.length, nextCursor: start > 0 ? cursor + items.length : null })
    }
    if (path === '/workflows/global-variables') return response({ variables: run?.variables ?? lastVariables, count: Object.keys(run?.variables ?? lastVariables).length })
    if (path.endsWith('/data/full') || path === '/workflows/data-latest/full') { const id=path==='/workflows/data-latest/full' ? Array.from(runRows.keys()).at(-1) : path.split('/')[2];const rows=runRows.get(id || '') || [];return response({workflow_id:id, rows, columns:Object.keys(rows[0] || {}),total:rows.length}) }
    if (path === '/workflows') {
      if (method === 'GET') return response(Object.values(db.workflows))
      const id = String(body.id || crypto.randomUUID())
      persist({ ...db, workflows: { ...db.workflows, [id]: { ...body, id } } })
      return response({ ...body, id })
    }
    const workflow = path.match(/^\/workflows\/([^/]+)(.*)$/)
    if (workflow) {
      const [, id, action] = workflow
      if (action === '' && method === 'PUT') {
        persist({ ...db, workflows: { ...db.workflows, [id]: { ...body, id } } }); return response({ ...body, id })
      }
      if (action === '/variable-tracking') {
        if (method === 'DELETE') { tracking.set(id, []); return response({message:'变量追踪记录已清空'}) }
        if (method !== 'GET') return failure('变量追踪只接受 GET 或 DELETE 请求',405)
        const records = tracking.get(id) || []
        return response({tracking:records,count:records.length,mock:true})
      }
      if (action === '/export-playwright' || action === '/export-script') return response({ code: '# Mock 导出：本文件用于校验下载交互，并非可运行脚本\n# Workflow: ' + String(db.workflows[id]?.name), filename: 'mock-workflow.txt', target: 'mock' })
      if (action === '/execute') return startRun(id, db.workflows[id], body)
      if (action === '/stop') return stopRun(id)
      if (action.startsWith('/debug/')) {
        if (!['/debug/resume', '/debug/step', '/debug/breakpoints', '/debug/variables'].includes(action)) return failure('未知调试操作', 404)
        if (method !== 'POST') return failure('调试操作只接受 POST 请求', 405)
        if (action === '/debug/breakpoints') {
          if (!run || run.id !== id) return failure('没有活跃运行',409)
          if (!validBreakpoints(body.breakpoints, run.nodeIds)) return failure('断点必须是运行快照中的节点标识数组', 422)
          run.breakpoints = [...body.breakpoints]
          return response({success:true})
        }
        if(action==='/debug/variables'){
          if(!isDebugVariablesRequest(body))return failure('变量修改内容或暂停身份无效',422)
          const fingerprint=JSON.stringify(['debug-variables',id,body])
          return applyIdentifiedCommand(body.commandId,fingerprint,()=>{
            const receipt={...body,workflowId:id}
            if(!run || run.id!==id || run.runId!==body.runId || !run.paused || run.pauseId!==body.pauseId || run.controlRevision!==body.controlRevision){
              return response({...receipt,success:false,error:'暂停上下文已过期或运行未暂停'},409)
            }
            const now=new Date().toISOString(),records=tracking.get(id)||[]
            for(const change of body.changes){
              const exists=Object.hasOwn(run.variables,change.name),oldValue=exists?run.variables[change.name]:null
              const nextValue=structuredClone(change.value) as Json
              run.variables[change.name]=nextValue
              records.push({timestamp:now,variable_name:change.name,old_value:oldValue,new_value:nextValue,node_id:String(run.nodes[run.index]?.id||''),node_name:'[Mock] 人工调试修改',operation:exists?'update':'create',value_type:nextValue===null?'null':Array.isArray(nextValue)?'array':typeof nextValue})
            }
            tracking.set(id,records)
            run.controlRevision++
            const node=run.nodes[run.index]||{},nodeId=String(node.id||'')
            emitMockEvent('execution:paused',{workflowId:id,runId:run.runId,pauseId:run.pauseId,controlRevision:run.controlRevision,node_id:nodeId,label:(node.data as ObjectValue|undefined)?.label??node.type,variables:structuredClone(run.variables),variableMeta:currentVariableMeta(run),reason:run.step?'step':'breakpoint'})
            return response({...receipt,success:true,error:null})
          })
        }
        if(!isDebugControlRequest(body))return failure('缺少有效的调试命令和暂停标识',422)
        const controlAction=action==='/debug/step'?'step':'resume'
        const fingerprint=JSON.stringify(['debug',id,body.runId,controlAction,body.commandId,body.pauseId,body.controlRevision])
        return applyIdentifiedCommand(body.commandId,fingerprint,()=>{
          const receipt={...body,workflowId:id,action:controlAction}
          if(!run || run.id!==id || run.runId!==body.runId || !run.paused || run.pauseId!==body.pauseId || run.controlRevision!==body.controlRevision) {
            return response({...receipt,success:false,error:'暂停上下文已过期或运行未暂停'},409)
          }
          run.step=controlAction==='step'
          run.controlRevision++
          emitMockEvent('execution:resumed',{workflowId:id,runId:run.runId,pauseId:body.pauseId,controlRevision:run.controlRevision})
          tick(true)
          return response({...receipt,success:true,error:null})
        })
      }
      if (!action && method === 'GET') return db.workflows[id] ? response(db.workflows[id]) : failure('工作流不存在',404)
      if (!action && method === 'DELETE') { const workflows = { ...db.workflows }; delete workflows[id]; persist({ ...db, workflows }); return response({success:true}) }
    }
    const scriptTest = mockBrowserScriptTests(path,method,body,browser && !run && !recording && !picking,url)
    if(scriptTest)return scriptTest
    if(path==='/v1/profiles'&&method==='GET')return response({items:mockBrowserProfiles,total:mockBrowserProfiles.length})
    if(path==='/browser/pages'){
      if(!browser)return response({error:'自动化浏览器未打开'},409)
      if(method==='GET')return response(browserPageState())
      if(method!=='POST')return response({error:'方法不允许'},405)
      if(body.sessionId!==browserSessionId || body.expectedRevision!==browserPageRevision)return response({error:'浏览器页面已变化，请刷新后重试'},409)
      const page=browserPages.find(page=>page.pageId===body.pageId)
      if(!page)return response({error:'目标页面已关闭，请重新选择'},409)
      if(!['select','focus','navigate'].includes(String(body.action)))return response({error:'页面操作无效'},400)
      if(body.action==='navigate'){
        if(typeof body.url!=='string' || !/^(https?:\/\/|about:blank$)/i.test(body.url))return response({error:'页面地址无效'},400)
        if(targetPageId!==page.pageId)return response({error:'请先明确选择目标页面'},409)
        page.url=body.url;url=body.url
      }
      if(body.action!=='focus'){
        targetPageId=page.pageId;browserPageRevision++
        closePickerSession();invalidateMockScriptTests(false)
      }
      return response(browserPageState())
    }
    if (path === '/browser/status') return response({ isOpen: browser, pickerActive:picking, pickerSessionId, url, mock: true })
    if (path === '/browser/chromium-status') return response({ installed: true, ready: true, mock: true })
    if (['/browser/open','/browser/launch','/browser/navigate'].includes(path)) {
      if(body.profileId!==undefined && !mockBrowserProfiles.some(profile=>profile.id===body.profileId))return response({error:'浏览器配置已不存在，请刷新后重试'},404)
      invalidateMockScriptTests(!browser)
      if(!browser){browserSessionId=crypto.randomUUID();browserPageRevision=0;targetPageId=crypto.randomUUID();browserPages=[{pageId:targetPageId,title:'空白页',url:'about:blank'}]}
      browser=true;url=String(body.url||url)
      const target=browserPages.find(page=>page.pageId===targetPageId)
      if(target){target.url=url;browserPageRevision++}
      return response({success:true,isOpen:true,url,mock:true})
    }
    if (path === '/browser/close') { invalidateMockScriptTests(true); browser = false; browserPages=[];targetPageId=null;browserPageRevision++;closePickerSession(); recording = false; return response({success:true}) }
    if (path === '/browser/get-selector') return response({success:true,selector:'#submit',mock:true})
    if (path === '/browser/url') return response({ url })
    const recordingReview = path.match(/^\/recorder\/reviews\/([^/]+)$/)
    if(recordingReview){
      const id=decodeURIComponent(recordingReview[1])
      const previous=db.recordingReviews?.[id]
      if(method==='GET')return previous?response(previous):failure('尚无已保存的录制审查',404)
      if(method!=='PUT')return failure('录制审查仅支持 GET/PUT',405)
      if(!Number.isSafeInteger(body.expectedRevision)||Number(body.expectedRevision)<0||typeof body.autoWait!=='boolean'||!Array.isArray(body.events)||body.events.some(event=>!event||typeof event!=='object'||Array.isArray(event)||!Number.isSafeInteger(event.sequence)||Number(event.sequence)<1||!['navigate','click','dblclick','input','select','check','keypress','drag','upload','scroll'].includes(String(event.type)))||Object.keys(body).some(key=>!['events','autoWait','expectedRevision'].includes(key)))return failure('录制审查格式无效',422)
      if(Number(previous?.revision||0)!==body.expectedRevision)return failure('录制审查已由其他窗口修改；保留本地步骤，请重新读取后核对',409)
      const saved={documentId:id,revision:Number(body.expectedRevision)+1,autoWait:body.autoWait,events:body.events}
      persist({...db,recordingReviews:{...db.recordingReviews,[id]:saved}})
      return response(saved)
    }
    if (path === '/recorder/start') {
      if(method!=='POST')return failure('启动录制仅支持 POST',405)
      const sessionId = typeof body.sessionId === 'string' && body.sessionId.trim() ? body.sessionId : null
      if(!sessionId||Object.keys(body).some(key=>key!=='sessionId'))return failure('录制启动参数无效',422)
      if (retiredRecordings.has(sessionId)) return failure('Recording session expired', 409)
      if (sessionId === recordingSessionId) return response({ success: true, sessionId, recording, nextSeq: recorded.length })
      if (!browser || run || picking || recording || mockScriptTestBusy()) return failure('请先打开空闲的 Mock 浏览器', 409)
      if (recordingSessionId) retiredRecordings.add(recordingSessionId)
      recordingSessionId = sessionId; recording = true; recorded = []
      return response({ success: true, sessionId, recording: true, nextSeq: 0 })
    }
    if (path === '/recorder/events' || path === '/recorder/stop') {
      if(method!==(path==='/recorder/events'?'GET':'POST'))return failure('录制操作 HTTP 方法错误',405)
      const requestedSession = method === 'POST' ? body.sessionId : target.searchParams.get('sessionId')
      if(typeof requestedSession!=='string'||!requestedSession.trim())return failure('缺少录制会话标识',422)
      if (requestedSession !== recordingSessionId) return failure('Recording session expired', 409)
      const afterSeq = Number(method === 'POST' ? body.afterSeq || 0 : target.searchParams.get('afterSeq') || 0)
      if (!Number.isSafeInteger(afterSeq) || afterSeq < 0 || afterSeq > recorded.length) return failure('Invalid recording cursor', 400)
      const limit=Number(method==='POST'?body.limit||200:target.searchParams.get('limit')||200)
      if(!Number.isSafeInteger(limit)||limit<1||limit>500)return failure('录制分页大小无效',422)
      const data = recorded.filter(event => Number(event.sequence) > afterSeq).slice(0,limit)
      const nextSeq=data.length?Number(data.at(-1)?.sequence):afterSeq
      const hasMore=nextSeq<recorded.length
      if (path === '/recorder/stop') { recording = false; return response({ success: true, sessionId: recordingSessionId, nextSeq, hasMore, data: { events: data } }) }
      return response({ success: true, sessionId: recordingSessionId, nextSeq, hasMore, data })
    }
    if (path === '/recorder/status') {
      if(method!=='GET')return failure('录制状态仅支持 GET',405)
      const requested=target.searchParams.get('sessionId')
      if(requested!==null&&!requested.trim())return failure('录制会话标识无效',422)
      if(requested&&requested!==recordingSessionId)return failure('录制会话不存在或已过期',409)
      return response({success:true,recording,isRecording:recording,sessionId:recordingSessionId,nextSeq:recorded.length})
    }
    if (path === '/element-picker/start') {
      if (method !== 'POST') return failure('启动拾取仅支持 POST', 405)
      const sessionId = pickerSessionFrom(target, body, method)
      if (!sessionId) return failure('缺少拾取会话标识', 422)
      if ((body.url != null && typeof body.url !== 'string') ||
          (body.browserConfig != null && (typeof body.browserConfig !== 'object' || Array.isArray(body.browserConfig))) ||
          Object.keys(body).some(key => !['sessionId','url','browserConfig'].includes(key))) return failure('拾取启动参数格式错误',422)
      const fingerprint = JSON.stringify({ url: body.url ?? null, browserConfig: body.browserConfig ?? null })
      if (sessionId === pickerSessionId) return pickerRequestFingerprint === fingerprint
        ? response({ ...pickerState(sessionId, true), isPicking: true })
        : failure('拾取会话 ID 已用于不同的启动参数', 409)
      if (retiredPickerSessions.has(sessionId)) return failure('拾取会话已结束', 409)
      if (pickerSessionId || run || recording || mockScriptTestBusy()) return failure('Mock 浏览器被占用',409)
      browser = true; picking = true; pickerSessionId = sessionId; pickerRequestFingerprint = fingerprint; picked = null; similarPicked = null
      return response({ ...pickerState(sessionId, true), isPicking: true })
    }
    if (path === '/element-picker/stop') {
      if (method !== 'POST') return failure('停止拾取仅支持 POST', 405)
      const sessionId = pickerSessionFrom(target, body, method)
      if (!sessionId) return failure('缺少拾取会话标识', 422)
      if (Object.keys(body).some(key => key !== 'sessionId')) return failure('拾取停止参数格式错误',422)
      if (sessionId !== pickerSessionId) {
        if (!pickerSessionId && retiredPickerSessions.has(sessionId)) return response(pickerState(sessionId, false))
        return failure('停止请求不属于当前拾取会话', 409)
      }
      if (failNextPickerStop) { failNextPickerStop = false; return failure('Mock 拾取清理失败，请重试', 503) }
      closePickerSession()
      return response(pickerState(sessionId, false))
    }
    if (path === '/element-picker/status') {
      if (method !== 'GET') return failure('拾取状态仅支持 GET', 405)
      const requested = pickerSessionFrom(target, body, method)
      if (requested && requested !== pickerSessionId) {
        if (retiredPickerSessions.has(requested)) return response(pickerState(requested, false))
        return failure('拾取会话不存在或已失效', 409)
      }
      const sessionId = pickerSessionId || requested || 'none'
      return response({ ...pickerState(sessionId, picking), isPicking:picking })
    }
    if (['/element-picker/result','/element-picker/selected'].includes(path)) {
      if (method !== 'GET') return failure('拾取结果仅支持 GET', 405)
      const requested = pickerSessionFrom(target, body, method)
      if (pickerSessionId && requested !== pickerSessionId) return failure('拾取结果不属于当前会话', 409)
      if (requested && !pickerSessionId) {
        if (retiredPickerSessions.has(requested)) return response(pickerState(requested, false))
        return failure('拾取会话不存在或已失效', 409)
      }
      const sessionId = pickerSessionId || 'none'
      return response({ ...pickerState(sessionId, picking), selected:picked !== null, data:picked, element:picked, ...picked })
    }
    if (path === '/element-picker/similar') {
      if (method !== 'GET') return failure('相似元素查询仅支持 GET', 405)
      const requested = pickerSessionFrom(target, body, method)
      if (pickerSessionId && requested !== pickerSessionId) return failure('相似元素结果不属于当前会话', 409)
      if (requested && !pickerSessionId) {
        if (retiredPickerSessions.has(requested)) return response(pickerState(requested, false))
        return failure('拾取会话不存在或已失效', 409)
      }
      const sessionId = pickerSessionId || 'none'
      return response({ ...pickerState(sessionId, picking), selected:similarPicked !== null, ...(picking && similarPicked ? { similar: similarPicked } : {}) })
    }
    if (path === '/element-picker/test-selector') {
      if (method !== 'POST') return failure('定位测试仅支持 POST', 405)
      if (typeof body.selector !== 'string' || !body.selector.trim() ||
          (body.highlight !== undefined && typeof body.highlight !== 'boolean') ||
          (body.hints != null && (typeof body.hints !== 'object' || Array.isArray(body.hints)))) return failure('定位测试参数格式错误', 422)
      if (body.sessionId != null && body.sessionId !== pickerSessionId) return failure('定位测试不属于当前拾取会话', 409)
      if (!browser) return failure('浏览器未打开，请先启动浏览器或元素拾取后再测试', 200)
      if (selectorTest === 'error') return failure('Mock 定位失败（显式服务失败场景，未查询网页）', 200)
      const count = selectorTest === 'none' ? 0 : selectorTest === 'multiple' ? 4 : 1
      return response({ success: true, matched: count > 0, count,
        tried: [{ selector: body.selector, count }],
        ...(count ? { matchedSelector: body.selector, isPrimary: true, element: { tag: 'button', text: 'Mock 定位结果（未查询网页）' } } : {}),
      })
    }
    if (path === '/custom-modules' || path === '/custom-modules/import') {
      if (method === 'GET') return response({ success:true, modules:Object.values(db.modules), total:Object.keys(db.modules).length })
      const id = String(body.id || crypto.randomUUID()); const module = {...body,id}; persist({...db,modules:{...db.modules,[id]:module}}); return response(module)
    }
    if (path.startsWith('/custom-modules/')) {
      const id = path.split('/')[2]
      if (path.endsWith('/duplicate')) { const original=db.modules[id];if(!original)return failure('Module not found',404);const copy={...structuredClone(original),id:crypto.randomUUID(),name:String(body.new_name || original.name)+' copy'};persist({...db,modules:{...db.modules,[String(copy.id)]:copy}});return response(copy) }
      if (path.endsWith('/increment-usage')) { const original=db.modules[id];if(!original)return failure('Module not found',404);persist({...db,modules:{...db.modules,[id]:{...original,usage_count:Number(original.usage_count || 0)+1}}});return response({success:true}) }
      if (method === 'DELETE') { const modules={...db.modules}; delete modules[id]; persist({...db,modules}); return response({success:true}) }
      if (method === 'PUT') { if (!db.modules[id]) return failure('模块不存在',404); persist({...db,modules:{...db.modules,[id]:{...db.modules[id],...body,id}}}); return response(db.modules[id]) }
      return db.modules[id] ? response(db.modules[id]) : failure('模块不存在',404)
    }
    if (path === '/workflow-bundle/export') {
      const content = body.content as ObjectValue
      if (!Array.isArray(content?.nodes)) return failure('Invalid workflow bundle')
      const serialized = JSON.stringify(content)
      const library = JSON.parse(localStorage.getItem('autoflow:studio:mock:image-assets') || '{"assets":[]}') as {assets:ObjectValue[]}
      return response({success:true,bundle:{type:'webrpa-workflow-bundle',version:1,name:body.name,exportedAt:new Date().toISOString(),workflow:content,
        customModules:Object.values(db.modules).filter(module=>serialized.includes(String(module.id))),
        images:library.assets.filter(asset=>serialized.includes(String(asset.id))).map(asset=>({id:asset.id,name:asset.name,originalName:asset.originalName,folder:asset.folder,ext:asset.extension,dataB64:String(asset.dataUrl).split(',')[1]}))}})
    }
    if (path === '/workflow-bundle/import') {
      const bundle=body.bundle as ObjectValue
      if(bundle?.type!=='webrpa-workflow-bundle' || !Array.isArray((bundle.workflow as ObjectValue)?.nodes))return failure('Invalid workflow bundle')
      const modules={...db.modules};let restoredModules=0
      for(const module of (bundle.customModules || []) as ObjectValue[]){const id=String(module.id);if(!modules[id]){modules[id]=module;restoredModules++}}
      const assetKey='autoflow:studio:mock:image-assets'
      const library=JSON.parse(localStorage.getItem(assetKey) || '{"assets":[],"folders":[]}') as {assets:ObjectValue[];folders:string[]}
      let restoredImages=0
      for(const asset of (bundle.images || []) as ObjectValue[]){
        if(library.assets.some(existing=>existing.id===asset.id))continue
        const ext=String(asset.ext || 'png').replace(/^\./,'')
        const dataUrl=`data:image/${ext==='jpg'?'jpeg':ext};base64,${asset.dataB64}`
        const size=atob(String(asset.dataB64 || '')).length
        if(size>2*1024*1024)return failure('Mock image exceeds 2 MiB',413)
        library.assets.push({...asset,path:dataUrl,url:dataUrl,dataUrl,size,filename:asset.name,createdAt:new Date().toISOString()})
        const folder=String(asset.folder || '');if(folder&&!library.folders.includes(folder))library.folders.push(folder)
        restoredImages++
      }
      persist({...db,modules});localStorage.setItem(assetKey,JSON.stringify(library))
      return response({success:true,name:bundle.name,workflow:bundle.workflow,restored:{customModules:restoredModules,images:restoredImages}})
    }
    if (path === '/feature-packs/preflight') return response({ok:true,missing:[],mock:true})
    if (path === '/system/set-clipboard') { await navigator.clipboard.writeText(String(body.text)); return response({success:true}) }
    if (path === '/system/select-folder' || path === '/system/select-file') {
      if(method!=='POST')return failure('Method not allowed',405)
      const kind=path.endsWith('select-file')?'file':'folder'
      if(!isPathSelectionRequest(body,kind))return failure('路径选择参数格式错误',422)
      return response(kind==='file'?{success:true,path:'mock://AutoFlow/example.csv',file:'mock://AutoFlow/example.csv'}:{success:true,path:db.folder,folder:db.folder})
    }
    if (path === '/system/browser-config' || path === '/system/config') { const configKey=key+path; if(method==='POST')localStorage.setItem(configKey,JSON.stringify(body.config || body));return response({success:true,config:JSON.parse(localStorage.getItem(configKey)||'{}'),mock:true}) }
    if (path === '/system/custom-hotkeys') return response({success:true,mock:true})
    if (path === '/local-workflows/self-heal' || path.startsWith('/local-workflows/self-heal/')) {
      const filename = method === 'POST' ? String(body.filename || '') : path.slice('/local-workflows/self-heal/'.length)
      const original = findFile(filename)
      if (!original) return failure('Workflow not found', 404)
      const selfHeal = { ...original.content.selfHeal as ObjectValue }
      if (method === 'POST') {
        if (typeof body.enabled !== 'boolean') return failure('enabled must be boolean', 422)
        selfHeal.enabled = body.enabled
        const content = { ...original.content, selfHeal }
        persist({ ...db, files: { ...db.files, [fileKey(filename)]: { ...original, content, modifiedTime: new Date().toISOString(), size: new Blob([JSON.stringify(content)]).size } } })
      } else if (method !== 'GET') return failure('Method not allowed', 405)
      return response({ success: true, enabled: selfHeal.enabled === true, selfHeal, mock: true })
    }
    if (path === '/system/module-required-fields') {
      if (method !== 'GET') return failure('只支持读取字段规则',405)
      if (failNextRequiredFields) { failNextRequiredFields = false; return failure('模拟字段规则服务暂不可用',503) }
      return response(requiredFieldMetadata)
    }
    if (path === '/system/info') return response({ platform:'mock', version:'AutoFlow Studio Mock', mock:true })
    if (path.startsWith('/security/')) return failure('独立令牌接口已停用；访问鉴权由 AutoFlow 宿主统一管理', 410)
    if (path === '/image-assets' || path === '/data-assets') return response({assets:[],folders:[]})
    if (path === '/plugins/installed' || path === '/plugins/market') return response({success:true,plugins:[],mock:true})
    if (path === '/feature-packs') return response({success:true,packs:[],mock:true})
    if (path === '/plugins') return response({plugins:[]})
    // Unknown routes are visible failures, never generic success or an accidental external request.
    return failure(`Mock 尚未实现：${method} ${path}`, 501)
  } catch (error) { return failure(error instanceof Error ? error.message : 'Mock 请求失败',500) }
}
