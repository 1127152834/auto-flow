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
interface Database {
  workflows: Record<string, ObjectValue>
  files: Record<string, SavedFile>
  modules: Record<string, ObjectValue>
  folder: string
}
const key = 'autoflow:studio:mock:database:v1'
const empty = (): Database => ({ workflows: {}, files: {}, modules: {}, folder: 'mock://AutoFlow/workflows' })
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
const runRows = new Map<string, ObjectValue[]>()
const tracking = new Map<string, ObjectValue[]>()
let lastVariables: ObjectValue = {}
let browser = false
let url = 'about:blank'
let recording = false
let recorded: ObjectValue[] = []
let recordingSessionId: string | null = null
const retiredRecordings = new Set<string>()
let picking = false
let picked: ObjectValue | null = null
let run: { id: string; nodes: ObjectValue[]; index: number; paused: boolean; step: boolean; breakpoints: string[]; variables: ObjectValue; timer?: ReturnType<typeof setTimeout> } | null = null
const commandResults = new Map<string, { fingerprint: string; response: ObjectValue }>()
const response = (data: unknown, status = 200) => Response.json(data, { status })
const failure = (message: string, status = 400) => response({ success: false, error: message, detail: message }, status)
const encode = (e: EventRecord) => encoder.encode(`id: ${e.sequence}\nevent: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`)
export function emitMockEvent(event: string, data: unknown) {
  const e = { sequence: events.length + 1, event, data }
  events.push(e)
  for (const stream of streams) stream.enqueue(encode(e))
}
function persist(next: Database) { localStorage.setItem(key, JSON.stringify(next)); db = next }
export function configureMock(options: { offline?: boolean; failNextSave?: boolean; failNextRun?: boolean; disconnect?: boolean }) {
  if (options.offline !== undefined) offline = options.offline
  if (options.failNextRun !== undefined) failNextRun = options.failNextRun
  if (options.failNextSave !== undefined) failNextSave = options.failNextSave
  if (options.disconnect || options.offline) {
    for (const stream of streams) stream.close()
    streams.clear()
  }
}
export function mockSnapshot() { return { offline, browser, recording, picking, url, run: run?.id ?? null, sequence: events.length } }
export function addMockRecordingEvent(event: ObjectValue) {
  if (!recording) throw new Error('请先在录制面板开始录制')
  recorded.push({ ...event, ts: Date.now(), sequence: recorded.length + 1 })
}
export function selectMockElement(selector: string) {
  if (!picking) throw new Error('请先开启元素拾取')
  picked = { selector, tag: 'button', tagName:'BUTTON', attributes:{id:selector.replace(/^#/, '')}, text: 'Mock 目标', hints: { selectors: [selector] } }
}
function finish(status: string) {
  if (!run) return
  clearTimeout(run.timer)
  emitMockEvent('execution:completed', { workflowId: run.id, result: { status, executedNodes: run.index, failedNodes: status === 'failed' ? 1 : 0 } })
  finishScheduledFixture(run.id, status, run.index)
  lastVariables = structuredClone(run.variables)
  run = null
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
    emitMockEvent('execution:paused', { workflowId: current.id, node_id: nodeId, label: data?.label ?? node.type, variables: current.variables, reason: current.step ? 'step' : 'breakpoint' })
    return
  }
  current.paused = false
  emitMockEvent('execution:node_start', { workflowId: current.id, nodeId })
  current.timer = setTimeout(() => {
    if (run !== current) return
    emitMockEvent('execution:log', { workflowId: current.id, log: { id: crypto.randomUUID(), timestamp: new Date().toISOString(), level: 'info', nodeId, message: `[Mock] 已模拟 ${data?.label ?? node.type} 的事件；未执行网页动作`, duration: 300, isSystemLog: true } })
    if (failNextRun) {
      failNextRun = false
      emitMockEvent('execution:log', { workflowId: current.id, log: { id: crypto.randomUUID(), timestamp:new Date().toISOString(),nodeId,level:'error',message:'[Mock] Simulated node failure',isSystemLog:true } })
      emitMockEvent('execution:node_complete', {workflowId:current.id,nodeId,success:false})
      finish('failed');return
    }
    emitMockEvent('execution:node_complete', {workflowId:current.id,nodeId,success:true})
    if (String(node.type) === 'get_element_info' || String(node.type) === 'extract_table_data') {
      const row = { mock:true, nodeId, value:'Mock result', index:current.index+1 }
      runRows.get(current.id)?.push(row)
      emitMockEvent('execution:data_row', {workflowId:current.id,row})
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
function startRun(id: string, doc: ObjectValue | undefined, body: ObjectValue): Response {
        if (run || recording || picking) return failure('Mock 浏览器正被运行、录制或拾取占用', 409)
        if (!doc) return failure('工作流不存在', 404)
        // Protocol fixture deliberately visits source order; it is not a replacement execution engine.
        const nodes = structuredClone(doc.nodes) as ObjectValue[]
        if (findExcludedModuleType(nodes, moduleId => {
          const children = (db.modules[moduleId]?.workflow as ObjectValue | undefined)?.nodes
          return Array.isArray(children) ? children : undefined
        })) return failure('工作流包含已排除节点', 422)
        const index = body.startNodeId ? nodes.findIndex(n => n.id === body.startNodeId) : 0
        if (index < 0) return failure('起点不存在')
        runRows.set(id, [])
        run = { id, nodes, index, paused: false, step: body.stepMode === true, breakpoints: (body.breakpoints || []) as string[], variables: Object.fromEntries(((doc.variables || []) as ObjectValue[]).map(v => [String(v.name), v.value])) }
        tracking.set(id,Object.entries(run.variables).map(([name,value])=>({timestamp:new Date().toISOString(),variable_name:name,old_value:null,new_value:value,node_id:'',node_name:'[Mock] Initial values',operation:'create',value_type:typeof value})))
        run.timer = setTimeout(() => { if (run?.id === id) { emitMockEvent('execution:started', { workflowId: id }); tick() } }, 30)
        return response({ success: true, workflowId: id, mock: true })
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
    if (path === '/events/stream') return streamResponse(Number(target.searchParams.get('afterSeq') || 0), signal)
    if (path === '/events/commands') {
      const id = String(body.commandId)
      const fingerprint = JSON.stringify(body)
      const previous = commandResults.get(id)
      if (previous) return previous.fingerprint === fingerprint ? response(previous.response) : failure('命令 ID 冲突', 409)
      if (body.event === 'execution_stop') finish('stopped')
      const result = { success: true, commandId: id }
      commandResults.set(id, { fingerprint, response: result })
      return response(result)
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
      if (action === '/variable-tracking') { if(method === 'DELETE') tracking.delete(id); return response({tracking:tracking.get(id) || [], mock:true}) }
      if (action === '/export-playwright' || action === '/export-script') return response({ code: '# Mock 导出：本文件用于校验下载交互，并非可运行脚本\n# Workflow: ' + String(db.workflows[id]?.name), filename: 'mock-workflow.txt', target: 'mock' })
      if (action === '/execute') return startRun(id, db.workflows[id], body)
      if (action === '/stop') { finish('stopped'); return response({ success: true }) }
      if (action.startsWith('/debug/')) {
        if (!run || run.id !== id) return failure('没有活跃运行', 409)
        if (action === '/debug/breakpoints') run.breakpoints = body.breakpoints as string[]
        else {
          if (!run.paused) return failure('运行未暂停', 409)
          run.step = action.endsWith('/step'); emitMockEvent('execution:resumed', { workflowId: id }); tick(true)
        }
        return response({ success: true })
      }
      if (!action && method === 'GET') return db.workflows[id] ? response(db.workflows[id]) : failure('工作流不存在',404)
      if (!action && method === 'DELETE') { const workflows = { ...db.workflows }; delete workflows[id]; persist({ ...db, workflows }); return response({success:true}) }
    }
    if (path === '/browser/status') return response({ isOpen: browser, pickerActive:picking, url, mock: true })
    if (path === '/browser/chromium-status') return response({ installed: true, ready: true, mock: true })
    if (['/browser/open','/browser/launch','/browser/navigate'].includes(path)) { browser = true; url = String(body.url || url); return response({ success: true, isOpen: true, url, mock: true }) }
    if (path === '/browser/close') { browser = false; picking = false; recording = false; return response({success:true}) }
    if (path === '/browser/get-selector') return response({success:true,selector:'#submit',mock:true})
    if (path === '/browser/url') return response({ url })
    if (path === '/recorder/start') {
      const sessionId = typeof body.sessionId === 'string' && body.sessionId ? body.sessionId : crypto.randomUUID()
      if (retiredRecordings.has(sessionId)) return failure('Recording session expired', 409)
      if (sessionId === recordingSessionId) return response({ success: true, sessionId, recording, nextSeq: recorded.length })
      if (!browser || run || picking || recording) return failure('请先打开空闲的 Mock 浏览器', 409)
      if (recordingSessionId) retiredRecordings.add(recordingSessionId)
      recordingSessionId = sessionId; recording = true; recorded = []
      return response({ success: true, sessionId, recording: true, nextSeq: 0 })
    }
    if (path === '/recorder/events' || path === '/recorder/stop') {
      const requestedSession = method === 'POST' ? body.sessionId : target.searchParams.get('sessionId')
      if (requestedSession && requestedSession !== recordingSessionId) return failure('Recording session expired', 409)
      const afterSeq = Number(method === 'POST' ? body.afterSeq || 0 : target.searchParams.get('afterSeq') || 0)
      if (!Number.isSafeInteger(afterSeq) || afterSeq < 0 || afterSeq > recorded.length) return failure('Invalid recording cursor', 400)
      const data = recorded.filter(event => Number(event.sequence) > afterSeq)
      if (path === '/recorder/stop') { recording = false; return response({ success: true, sessionId: recordingSessionId, nextSeq: recorded.length, data: { events: data } }) }
      return response({ success: true, sessionId: recordingSessionId, nextSeq: recorded.length, data })
    }
    if (path === '/recorder/status') return response({ recording, isRecording: recording, sessionId: recordingSessionId, nextSeq: recorded.length })
    if (path === '/element-picker/start') { if (run || recording) return failure('Mock 浏览器被占用',409); browser = true; picking = true; picked = null; return response({success:true}) }
    if (path === '/element-picker/stop') { picking = false; return response({success:true}) }
    if (path === '/element-picker/status') return response({ active:picking, isPicking:picking })
    if (['/element-picker/result','/element-picker/selected'].includes(path)) return response({ success:true, active:picking, selected:picked !== null, data:picked, element:picked, ...picked })
    if (path === '/element-picker/similar') return response({ success:true, elements:[] })
    if (path === '/element-picker/test-selector') return response({ success:true, matched:!!body.selector, count:body.selector ? 1:0, matchedSelector:body.selector, isPrimary:true, element:{tag:'button',text:'Mock 定位结果（未查询网页）'} })
    if (path === '/custom-modules' || path === '/custom-modules/import') {
      if (method === 'GET') return response({ success:true, modules:Object.values(db.modules), total:Object.keys(db.modules).length })
      const id = String(body.id || crypto.randomUUID()); const module = {...body,id}; persist({...db,modules:{...db.modules,[id]:module}}); return response(module)
    }
    if (path.startsWith('/custom-modules/')) {
      const id = path.split('/')[2]
      if (path.endsWith('/duplicate')) { const original=db.modules[id];if(!original)return failure('Module not found',404);const copy={...structuredClone(original),id:crypto.randomUUID(),name:String(body.new_name || original.name)+' copy'};persist({...db,modules:{...db.modules,[String(copy.id)]:copy}});return response(copy) }
      if (path.endsWith('/increment-usage')) { const original=db.modules[id];if(!original)return failure('Module not found',404);persist({...db,modules:{...db.modules,[id]:{...original,usage_count:Number(original.usage_count || 0)+1}}});return response({success:true}) }
      if (method === 'DELETE') { const modules={...db.modules}; delete modules[id]; persist({...db,modules}); return response({success:true}) }
      if (method === 'PUT') { persist({...db,modules:{...db.modules,[id]:{...body,id}}}); return response(db.modules[id]) }
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
    if (path === '/system/select-folder') return response({success:true,path:db.folder,folder:db.folder})
    if (path === '/system/select-file') return response({success:true,path:'mock://AutoFlow/example.csv',file:'mock://AutoFlow/example.csv'})
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
    if (path === '/system/info') return response({ platform:'mock', version:'AutoFlow Studio Mock', mock:true })
    if (path === '/security/status') return response({enabled:false,isLocal:true,token:null})
    if (path === '/image-assets' || path === '/data-assets') return response({assets:[],folders:[]})
    if (path === '/plugins/installed' || path === '/plugins/market') return response({success:true,plugins:[],mock:true})
    if (path === '/feature-packs') return response({success:true,packs:[],mock:true})
    if (path === '/plugins') return response({plugins:[]})
    // Unknown routes are visible failures, never generic success or an accidental external request.
    return failure(`Mock 尚未实现：${method} ${path}`, 501)
  } catch (error) { return failure(error instanceof Error ? error.message : 'Mock 请求失败',500) }
}
