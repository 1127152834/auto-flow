// Source: WebRPA@5ccb900e, components/workflow/RecorderPanel.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { nanoid } from 'nanoid'
import { RecorderStepEditor } from './RecorderStepEditor'
import { buildRecordedNodes, type RecEvent } from '../lib/recordingGeneration'
import { Circle, Square, X, MousePointerClick, Type, ChevronDown, CheckSquare, Globe, Wand2, Trash2, ArrowUp, ArrowDown, Clock, Keyboard, Move, Upload, MoveVertical } from 'lucide-react'
import { recorderApi, browserApi } from '../api'
import { registerDocumentLeaveResource,requestSessionTransition } from '../lib/documentLeave'
import {getStudioTransportRevision} from '../api/transport'
import { useWorkflowStore } from '../editor-store'
import { emitAssistantUiEvent } from '../api/aiAssistantSkills'
import { applySerpentineLayout } from '../lib/recorderLayout'
import { useConfirm } from './controls/confirm-dialog'
import { Checkbox } from './controls/checkbox'


interface RecorderPanelProps {
  open: boolean
  onClose: () => void
}

const EVENT_META: Record<string, { icon: any; label: string; color: string }> = {
  navigate: { icon: Globe, label: '打开网页', color: 'text-blue-500' },
  click: { icon: MousePointerClick, label: '点击', color: 'text-indigo-500' },
  dblclick: { icon: MousePointerClick, label: '双击', color: 'text-indigo-500' },
  input: { icon: Type, label: '输入', color: 'text-emerald-500' },
  select: { icon: ChevronDown, label: '下拉选择', color: 'text-violet-500' },
  check: { icon: CheckSquare, label: '勾选', color: 'text-amber-500' },
  keypress: { icon: Keyboard, label: '按键', color: 'text-rose-500' },
  drag: { icon: Move, label: '拖拽', color: 'text-teal-500' },
  upload: { icon: Upload, label: '上传文件', color: 'text-orange-500' },
  scroll: { icon: MoveVertical, label: '滚动', color: 'text-cyan-500' },
}

export function RecorderPanel({ open, onClose }: RecorderPanelProps) {
  const [recording, setRecording] = useState(false)
  const [events, setEvents] = useState<RecEvent[]>([])
  const [editing, setEditing] = useState<{index:number;event:RecEvent}|null>(null)
  const [preview, setPreview] = useState<ReturnType<typeof buildRecordedNodes>|null>(null)
  const [page,setPage] = useState(0)
  const [reviewRevision,setReviewRevision]=useState<{documentId:string;revision:number}|null>(null)
  const [savedReview,setSavedReview]=useState('')
  const savedReviewRef=useRef(savedReview)
  savedReviewRef.current=savedReview
  const reviewRevisionRef=useRef(reviewRevision)
  reviewRevisionRef.current=reviewRevision
  const shownPage=Math.min(page,Math.max(0,Math.ceil(events.length/100)-1))

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const documentId = useWorkflowStore(s=>s.id)
  const [connectionRevision,setConnectionRevision]=useState(getStudioTransportRevision)
  const originRef=useRef<{documentId:string;name:string;connection:number}|null>(null)
  const mountedRef=useRef(true)
  const commandBusyRef=useRef(false)
  const sessionRef = useRef<string | null>(null)
  const activeSessionRef = useRef<string | null>(null)
  const pendingStartRef = useRef<string | null>(null)
  const sequenceRef = useRef(0)
  const pollBusyRef = useRef(false)
  const pollAbortRef = useRef<AbortController | null>(null)
  const [autoWait, setAutoWait] = useState(true)
  const autoWaitRef=useRef(autoWait)
  autoWaitRef.current=autoWait
  const pollRef = useRef<number | null>(null)
  const eventsRef = useRef<RecEvent[]>([])
  const addLog = useWorkflowStore((s) => s.addLog)
  const { alert: alertDialog, confirm, ConfirmDialog } = useConfirm()
  const origin=originRef.current
  const originChanged=!!origin&&(origin.documentId!==documentId||origin.connection!==connectionRevision)

  useEffect(() => { eventsRef.current = events; setPreview(null) }, [events,autoWait])

  // 编辑：删除某步
  const deleteEvent = useCallback((idx: number) => {
    setEvents((prev) => prev.filter((_, i) => i !== idx))
  }, [])
  // 编辑：上移/下移
  const moveEvent = useCallback((idx: number, dir: -1 | 1) => {
    setEvents((prev) => {
      const j = idx + dir
      if (j < 0 || j >= prev.length) return prev
      const next = [...prev]
      const tmp = next[idx]; next[idx] = next[j]; next[j] = tmp
      return next
    })
  }, [])

  // 合并追加：连续的同选择器 input 只保留最后一次（需同一 frame，避免跨 frame 误合并）
  const appendEvents = useCallback((incoming: RecEvent[]) => {
    if (!incoming || !incoming.length) return
    const frameSig = (e?: RecEvent) => JSON.stringify(e?._frame || null)
      const next = [...eventsRef.current]
      for (const original of incoming) {
        const ev = original.type === 'input' && original.sensitive ? {...original,value:'',needsValue:true} : original
        const last = next[next.length - 1]
        if (ev.type === 'input' && last && last.type === 'input' && last.selector === ev.selector && frameSig(last) === frameSig(ev)) {
          next[next.length - 1] = ev
        } else if (ev.type === 'dblclick') {
          // 双击：移除紧邻的同选择器单击（跨轮询批次时后端可能已 drain，这里再兜底一次）
          let removed = 0
          while (next.length && removed < 2) {
            const l = next[next.length - 1]
            if (l && l.type === 'click' && l.selector === ev.selector && frameSig(l) === frameSig(ev)) { next.pop(); removed++ }
            else break
          }
          next.push(ev)
        } else if (ev.type === 'scroll' && last && last.type === 'scroll' && last.selector === ev.selector && frameSig(last) === frameSig(ev) && ((last.dy ?? 0) > 0) === ((ev.dy ?? 0) > 0)) {
          next[next.length - 1] = { ...last, dy: (last.dy ?? 0) + (ev.dy ?? 0), y: ev.y, ts: ev.ts }  // 合并连续同向滚动
        } else if (ev.type === 'navigate' && last && last.type === 'navigate' && last.url === ev.url && frameSig(last) === frameSig(ev)) {
          // 跳过重复导航
        } else {
          next.push(ev)
        }
      }
      eventsRef.current=next
      setEvents(next)
  }, [])

  const acceptBatch = useCallback((sessionId: string, response: any, stopping = false) => {
    if (!mountedRef.current||originRef.current?.connection!==getStudioTransportRevision()||sessionRef.current !== sessionId) throw new Error('录制会话上下文已失效，未应用步骤')
    if (!response.success || !response.data?.success) throw new Error(response.error || response.data?.error || '录制请求失败')
    const body = response.data
    if (body.sessionId !== sessionId) throw new Error('录制响应不属于当前会话')
    const incoming = stopping ? body.data?.events : body.data
    if (!Array.isArray(incoming) || !Number.isSafeInteger(body.nextSeq) || body.nextSeq < 0) throw new Error('录制响应的确认游标无效，请重试')
    // 服务保留原始确认序列；UI 合并输入等步骤后，仍按原序列补读。
    // 先检查整个批次，避免只应用前半批却确认了尚未收到的尾部。
    let previous: number | undefined
    let confirmed = sequenceRef.current
    const fresh: RecEvent[] = []
    for (const event of incoming) {
      if (!event || !Number.isSafeInteger(event.sequence) || event.sequence < 1 ||
          !Object.hasOwn(EVENT_META, event.type) ||
          (previous !== undefined && event.sequence !== previous + 1)) {
        throw new Error('录制事件序列无效，请重试')
      }
      previous = event.sequence
      if (event.sequence > confirmed) {
        if (event.sequence !== confirmed + 1) throw new Error('录制事件存在缺口，请重试补读')
        fresh.push(event)
        confirmed = event.sequence
      }
    }
    if (body.nextSeq !== (previous ?? sequenceRef.current)) throw new Error('录制确认游标与事件尾部不一致，请重试')
    appendEvents(fresh)
    sequenceRef.current = confirmed
    setError('')
  }, [appendEvents])

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    pollAbortRef.current?.abort()
    pollAbortRef.current = null
    pollBusyRef.current = false
  }, [])

  const startRecording = useCallback(async () => {
    if(commandBusyRef.current)return
    if(originRef.current&&originRef.current.connection!==getStudioTransportRevision()){
      setError('录制所属服务已变更，请关闭面板并在当前工作区重新开始')
      return
    }
    commandBusyRef.current=true
    setBusy(true)
    setError('')
    const sessionId = pendingStartRef.current || nanoid()
    const source=useWorkflowStore.getState()
    const owner=pendingStartRef.current&&originRef.current?originRef.current:{documentId:source.id,name:source.name,connection:getStudioTransportRevision()}
    originRef.current=owner
    const current=()=>mountedRef.current&&owner.connection===getStudioTransportRevision()&&useWorkflowStore.getState().id===owner.documentId
    try {
      if(!pendingStartRef.current&&!await requestSessionTransition(true))return
      pendingStartRef.current = sessionId
      if(eventsRef.current.length && !await confirm('开始新录制会替换当前审查步骤。请先保存需要保留的审查，是否继续？',{title:'开始新录制'})){pendingStartRef.current=null;return}
      if(!current()){pendingStartRef.current=null;return}
      // 录制前先检查自动化浏览器是否已启动，未启动则明确提示（不用浏览器原生弹窗）
      try {
        const st: any = await browserApi.getStatus()
        if(!current()){setError('流程或服务已变更，未启动录制');pendingStartRef.current=null;return}
        if (!st.success) { setError(st.error || '无法读取浏览器状态'); return }
        if (!st?.data?.isOpen) {
          setBusy(false)
          await alertDialog('请先启动自动化浏览器，再开始录制。可点击工具栏的「打开浏览器」按钮启动后重试。', {
            title: '自动化浏览器未启动', confirmText: '我知道了',
          })
          return
        }
      } catch (error) {
        setError(`浏览器状态查询失败：${String(error)}`)
        return
      }
      activeSessionRef.current = sessionId
      const res: any = await recorderApi.start(sessionId)
      if(!mountedRef.current||owner.connection!==getStudioTransportRevision())return
      if (res?.error || res?.success === false || res?.data?.success === false) {
        if(res.outcomeUnknown){
          sessionRef.current=sessionId
          sequenceRef.current=0
          setEvents([])
          setRecording(true)
          setError('录制启动尚未确认，请停止录制以确认尾部和释放占用')
          return
        }
        if(res.httpStatus&&res.httpStatus<500){ pendingStartRef.current=null; activeSessionRef.current=null }
        const errMsg = res?.data?.error || res?.error || '未知错误'
        setBusy(false)
        // 后端兜底：没有活跃浏览器等错误，用醒目弹窗提示
        await alertDialog(String(errMsg).includes('浏览器') ? '请先启动自动化浏览器，再开始录制。' : `录制启动失败：${errMsg}`, {
          title: '无法开始录制', confirmText: '我知道了',
        })
        addLog({ level: 'error', message: `录制启动失败：${errMsg}` })
        return
      }
      if (res.data?.sessionId !== sessionId || res.data?.recording !== true) throw new Error('服务未确认录制会话已启动')
      sessionRef.current = sessionId
      pendingStartRef.current = null
      sequenceRef.current = 0
      setEvents([])
      setRecording(true)
      if(!current()){setError(`录制属于「${owner.name}」，请先停止；步骤不会加入当前流程`);return}
      addLog({ level: 'success', message: '已开始录制，请在浏览器中操作（点击/输入/选择）' })
      stopPolling()
      pollRef.current = window.setInterval(async () => {
        if (pollBusyRef.current || sessionRef.current !== sessionId || !mountedRef.current || owner.connection!==getStudioTransportRevision()) return
        pollBusyRef.current = true
        const controller = new AbortController()
        pollAbortRef.current = controller
        try {
          const response = await recorderApi.events(sessionId, sequenceRef.current, controller.signal)
          if (!controller.signal.aborted) acceptBatch(sessionId, response)
        } catch (error) {
          if (!controller.signal.aborted && sessionRef.current === sessionId) setError(String(error))
        } finally { if (pollAbortRef.current === controller) { pollBusyRef.current = false; pollAbortRef.current = null } }
      }, 700)
    } catch (e) {
      addLog({ level: 'error', message: `录制启动异常：${e}` })
    } finally {
      commandBusyRef.current=false
      setBusy(false)
    }
  }, [addLog, acceptBatch, alertDialog, stopPolling, confirm])

  const stopRecording = useCallback(async () => {
    const sessionId = sessionRef.current
    if (!sessionId) return false
    if(commandBusyRef.current)return false
    if(originRef.current?.connection!==getStudioTransportRevision()){
      setError('录制所属服务已变更，停止请求未发送到新工作区')
      return false
    }
    commandBusyRef.current=true
    setBusy(true)
    try {
      const response = await recorderApi.stop(sessionId, sequenceRef.current)
      acceptBatch(sessionId, response, true)
      stopPolling()
      setRecording(false)
      activeSessionRef.current=null
      pendingStartRef.current=null
      addLog({ level: 'info', message: '录制已停止' })
      return true
    } catch (error) {
      setError(String(error))
      addLog({ level: 'error', message: `停止录制异常：${error}` })
      return false
    } finally { commandBusyRef.current=false;setBusy(false) }
  }, [addLog, acceptBatch, stopPolling])

  useEffect(() => registerDocumentLeaveResource(() => {
    const sessionId=activeSessionRef.current || (commandBusyRef.current?pendingStartRef.current:null)
    const owner=originRef.current
    const reviewDirty=(eventsRef.current.length>0||Boolean(savedReviewRef.current))&&savedReviewRef.current!==JSON.stringify([eventsRef.current,autoWaitRef.current])
    if(!owner||(!sessionId&&!reviewDirty))return null
    return {id:`recorder:${owner.connection}:${owner.documentId}:${sessionId||'review'}`,label:sessionId?'网页录制及审查':'未保存录制审查',release:async()=>{
      if(owner.connection!==getStudioTransportRevision()||owner.documentId!==originRef.current?.documentId)return false
      if(sessionId&&!(await stopRecording()))return false
      if(commandBusyRef.current)return false
      const signature=JSON.stringify([eventsRef.current,autoWaitRef.current])
      if((!eventsRef.current.length&&!savedReviewRef.current)||savedReviewRef.current===signature)return true
      const revision=reviewRevisionRef.current
      const result=await recorderApi.saveReview(owner.documentId,{expectedRevision:revision?.documentId===owner.documentId?revision.revision:0,autoWait:autoWaitRef.current,events:eventsRef.current as any})
      if(!result.success||!result.data||result.data.documentId!==owner.documentId||!Number.isSafeInteger(result.data.revision)||result.data.revision<1||owner.connection!==getStudioTransportRevision()){setError(result.error||'录制审查保存未确认，当前步骤已保留');return false}
      const next={documentId:owner.documentId,revision:result.data.revision}
      reviewRevisionRef.current=next;setReviewRevision(next)
      savedReviewRef.current=signature;setSavedReview(signature)
      return signature===JSON.stringify([eventsRef.current,autoWaitRef.current])
    }}
  }), [stopRecording])

  const reviewRequest = async (operation: 'save'|'read') => {
    if(commandBusyRef.current || recording || activeSessionRef.current || editing)return
    if(operation==='save' && originChanged){setError('审查属于原流程，不能保存到当前流程');return}
    const source=useWorkflowStore.getState()
    const revision=getStudioTransportRevision()
    const signature=JSON.stringify([eventsRef.current,autoWait])
    commandBusyRef.current=true;setBusy(true);setError('')
    const current=()=>mountedRef.current && source.id===useWorkflowStore.getState().id && revision===getStudioTransportRevision()
    try{
      if(operation==='read' && eventsRef.current.length && !await confirm('读取已保存审查会替换当前审查步骤，是否继续？',{title:'读取录制审查'}))return
      if(!current())return
      const result=operation==='read'?await recorderApi.readReview(source.id):await recorderApi.saveReview(source.id,{
        expectedRevision:reviewRevision?.documentId===source.id?reviewRevision.revision:0,
        autoWait,events:eventsRef.current as any,
      })
      if(!current())return
      if(!result.success)throw Error(result.error||'审查服务未确认成功')
      const data=result.data
      if(!data || data.documentId!==source.id || !Number.isSafeInteger(data.revision) || data.revision<1 || typeof data.autoWait!=='boolean' || !Array.isArray(data.events) || data.events.some(event=>!event||!Number.isSafeInteger(event.sequence)||event.sequence<1||!Object.hasOwn(EVENT_META,event.type)))throw Error('审查响应身份或结构无效')
      setReviewRevision({documentId:source.id,revision:data.revision})
      if(operation==='read'){
        if(signature!==JSON.stringify([eventsRef.current,autoWaitRef.current]))throw Error('读取期间审查已修改，已保留本地步骤')
        originRef.current={documentId:source.id,name:source.name,connection:revision}
        setEvents(data.events);setAutoWait(data.autoWait);setPage(0);setPreview(null)
        setSavedReview(JSON.stringify([data.events,data.autoWait]))
      }else setSavedReview(signature)
      addLog({level:'success',message:operation==='read'?'已恢复录制审查，未恢复或重放浏览器操作':'录制审查已保存；工作流仍需手动保存'})
    }catch(cause){setError(cause instanceof Error?cause.message:String(cause))}
    finally{commandBusyRef.current=false;setBusy(false)}
  }

  // 事件 → 节点
  const generateNodes = useCallback(async () => {
    const origin=originRef.current
    if(!origin||origin.documentId!==useWorkflowStore.getState().id||origin.connection!==getStudioTransportRevision()){
      setError('录制步骤属于其他流程或服务，不能加入当前画布')
      return
    }
    if (recording || busy || editing) return
    const evs = eventsRef.current
    if (evs.some(event=>event.needsValue)) { setError('敏感输入仍待补值，请先编辑对应步骤'); return }
    const newVariables = evs.filter(event=>event.variableName).map(event=>({name:event.variableName!,value:String(event.value??''),type:'string' as const,scope:'global' as const}))
    const names = new Set(useWorkflowStore.getState().variables.map(variable=>variable.name))
    for(const variable of newVariables){
      if(names.has(variable.name)){setError(`变量「${variable.name}」重复或已存在，请修改名称；没有写入画布`);return}
      names.add(variable.name)
    }
    if (!evs.length) {
      addLog({ level: 'warning', message: '没有录制到任何操作' })
      return
    }
    const {nodes: newNodes, edges: newEdges} = buildRecordedNodes(evs, autoWait)

    if (!newNodes.length) {
      addLog({ level: 'warning', message: '录制事件无法转换为有效节点' })
      return
    }

    const store = useWorkflowStore.getState()
    // 蛇形（横向长方形）排版：录制链纯竖排太长，改为逐行折返、连线自动拐弯
    applySerpentineLayout(newNodes as any, store.nodes as any)
    store.pushHistory()
    useWorkflowStore.setState({
      nodes: [...store.nodes, ...newNodes] as any,
      edges: [...store.edges, ...newEdges] as any,
      variables: [...store.variables, ...newVariables],
      hasUnsavedChanges: true,
    })
    emitAssistantUiEvent('fit_view', {})
    addLog({ level: 'success', message: `已根据录制生成 ${newNodes.length} 个节点` })
    eventsRef.current = []
    setEvents([])
    savedReviewRef.current = ''
    setSavedReview('')
    reviewRevisionRef.current = null
    setReviewRevision(null)
    originRef.current = null
    sessionRef.current = null
    sequenceRef.current = 0
    onClose()
  }, [addLog, onClose, autoWait, recording, busy, editing])

  useEffect(() => {
    mountedRef.current=true
    const changed=()=>{stopPolling();setConnectionRevision(getStudioTransportRevision())}
    window.addEventListener('studio:transport-changed',changed)
    return ()=>{mountedRef.current=false;stopPolling();window.removeEventListener('studio:transport-changed',changed)}
  }, [stopPolling])
  const closePanel = async () => {
    if (busy) return
    if(originRef.current&&originRef.current.connection!==getStudioTransportRevision()){
      if((recording||eventsRef.current.length)&&!await confirm('原工作区连接已切换。关闭将丢弃尚未生成的本地录制步骤，是否关闭？',{title:'关闭旧录制',confirmText:'丢弃并关闭'}))return
      stopPolling();setRecording(false);activeSessionRef.current=null;sessionRef.current=null;pendingStartRef.current=null;originRef.current=null;setEvents([]);setError('');onClose();return
    }
    if (recording && !await stopRecording()) return
    onClose()
  }

  if (!open) return null

  return (
    <>
    {createPortal(
    <div className="fixed bottom-20 right-5 z-[1000] w-[340px] rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] shadow-2xl overflow-hidden flex flex-col" style={{ maxHeight: '70vh' }}>
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[hsl(var(--border))] bg-[hsl(var(--brand-50))]">
        <Wand2 className="w-4 h-4 text-[hsl(var(--brand-600))]" />
        <span className="font-semibold text-sm">智能录制器</span>
        {recording && <span className="ml-1 flex items-center gap-1 text-xs text-red-500"><span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />录制中</span>}
        <button className="ml-auto p-1 rounded hover:bg-[hsl(var(--muted))]" aria-label="关闭录制器" disabled={busy} onClick={closePanel}><X className="w-4 h-4" /></button>
      </div>

      {error && <div role="alert" className="px-4 py-2 text-sm text-red-700">{error}</div>}
      {originChanged&&<div role="status" className="px-4 py-2 text-sm text-amber-700">录制属于「{origin?.name}」的原流程与服务，当前画布不可接收这些步骤。</div>}
      <div className="px-4 py-2 border-b border-[hsl(var(--border))] flex gap-2">
        {!recording ? (
          <button disabled={busy} onClick={startRecording} className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-red-500 text-white text-sm font-medium hover:bg-red-600 disabled:opacity-50">
            <Circle className="w-3.5 h-3.5 fill-current" /> 开始录制
          </button>
        ) : (
          <button disabled={busy} onClick={stopRecording} className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-slate-700 text-white text-sm font-medium hover:bg-slate-800 disabled:opacity-50">
            <Square className="w-3.5 h-3.5 fill-current" /> 停止录制
          </button>
        )}
        <button disabled={recording || busy || !!editing || !events.length || originChanged} onClick={generateNodes} className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg gradient-primary text-white text-sm font-medium disabled:opacity-50">
          <Wand2 className="w-3.5 h-3.5" /> 生成节点
        </button>
      </div>

      {!recording && <div className="px-3 py-2 text-xs flex gap-2">
        <button disabled={busy || !!editing || (!events.length&&!savedReview) || originChanged} onClick={()=>reviewRequest('save')}>保存审查</button>
        <button disabled={busy || !!editing} onClick={()=>reviewRequest('read')}>读取审查</button>
        {events.length>0&&<span>{savedReview===JSON.stringify([events,autoWait])?'审查已保存':'审查未保存'}</span>}
      </div>}
      {!recording && events.length > 0 && <div className="px-3 py-2 text-xs space-x-2">
        <button disabled={busy || !!editing || originChanged} onClick={()=>setPreview(buildRecordedNodes(events,autoWait))}>预览生成</button>
        <span>每页最多显示100步；原始内容完整保留</span>
      </div>}
      {editing && <RecorderStepEditor key={editing.index} event={editing.event} onCancel={()=>setEditing(null)} onApply={next=>{
        if(originChanged || recording || events[editing.index]!==editing.event){setError('步骤来源已变化，请重新编辑');setEditing(null);return}
        setEvents(previous=>previous.map((event,index)=>index===editing.index?next:event));setEditing(null);setError('')
      }}/>}
      {preview && <section aria-label="录制生成预览" className="max-h-48 overflow-auto px-3 py-2 text-xs">
        <strong>将生成 {preview.nodes.length} 个节点；尚未加入画布</strong>
        {preview.nodes.slice(0,100).map((node,index)=><div key={node.id}>{index+1}. {node.data.label} {String(node.data.url||node.data.text||node.data.selector||'')}</div>)}
        {preview.nodes.length>100&&<p>预览前100个；加入时包含全部节点。</p>}
        <button onClick={()=>setPreview(null)}>关闭预览</button>
      </section>}
      <div className="flex-1 overflow-y-auto px-2 py-2 min-h-[80px]">
        {events.length === 0 ? (
          <div className="text-center text-xs text-[hsl(var(--muted-foreground))] py-8 px-3">
            {recording ? '在浏览器里操作，步骤会实时出现在这里…' : '点击「开始录制」，然后在自动化浏览器里点击 / 输入 / 选择 / 按键，WebRPA 会自动记录成步骤。跳转新页面、新标签页也会持续录制。'}
          </div>
        ) : (
          <ol className="space-y-1">
            {events.slice(shownPage*100,(shownPage+1)*100).map((ev, offset) => {
              const i=shownPage*100+offset
              const meta = EVENT_META[ev.type] || EVENT_META.click
              const Icon = meta.icon
              const detail = ev.type === 'navigate' ? ev.url
                : ev.type === 'input' ? (ev.needsValue ? '待补值（原密码未保留）' : ev.sensitive ? '••••••（用户已补值）' : `"${String(ev.value ?? '').slice(0, 24)}"`)
                : ev.type === 'select' ? (ev.text || String(ev.value ?? ''))
                : ev.type === 'check' ? (ev.value ? '勾选' : '取消勾选')
                : ev.type === 'keypress' ? ev.key
                : ev.type === 'drag' ? `${ev.text || ev.selector} → ${ev.targetSelector}`
                : ev.type === 'upload' ? (ev.fileName ? ev.fileName + '（需补填路径）' : '需补填文件路径')
                : ev.type === 'scroll' ? `${(ev.dy ?? 0) >= 0 ? '向下' : '向上'} ${Math.abs(ev.dy ?? 0)}px`
                : (ev.text || ev.selector)
              return (
                <li key={i} className="group flex items-start gap-2 px-2 py-1.5 rounded hover:bg-[hsl(var(--muted))] text-xs">
                  <span className="text-[10px] text-[hsl(var(--muted-foreground))] w-4 text-right pt-0.5">{i + 1}</span>
                  <Icon className={`w-3.5 h-3.5 mt-0.5 flex-none ${meta.color}`} />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium">{meta.label}</div>
                    <div className="text-[hsl(var(--muted-foreground))] truncate" title={ev.selector || ev.url}>{detail}</div>
                  </div>
                  {!recording && !editing && (
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-none">
                      <button onClick={()=>setEditing({index:i,event:ev})} aria-label={`编辑第${i+1}步`}>编辑</button>
                      <button onClick={() => moveEvent(i, -1)} disabled={i === 0} title="上移" className="p-1 rounded hover:bg-[hsl(var(--accent))] disabled:opacity-30"><ArrowUp className="w-3 h-3" /></button>
                      <button onClick={() => moveEvent(i, 1)} disabled={i === events.length - 1} title="下移" className="p-1 rounded hover:bg-[hsl(var(--accent))] disabled:opacity-30"><ArrowDown className="w-3 h-3" /></button>
                      <button onClick={() => deleteEvent(i)} title="删除此步" className="p-1 rounded hover:bg-red-50 text-red-500"><Trash2 className="w-3 h-3" /></button>
                    </div>
                  )}
                </li>
              )
            })}
          </ol>
        )}
      </div>

      {events.length > 100 && <nav aria-label="录制步骤分页" className="px-3 py-2 text-xs flex gap-2">
        <button disabled={shownPage===0} onClick={()=>{setPage(shownPage-1);setEditing(null)}}>上一页步骤</button>
        <span>{shownPage+1} / {Math.ceil(events.length/100)}</span>
        <button disabled={(shownPage+1)*100>=events.length} onClick={()=>{setPage(shownPage+1);setEditing(null)}}>下一页步骤</button>
      </nav>}
      <div className="px-4 py-2 border-t border-[hsl(var(--border))] flex items-center justify-between text-[11px] text-[hsl(var(--muted-foreground))]">
        <span>共 {events.length} 步{recording ? ' · 录制中' : ' · 可拖删/排序后生成'}</span>
        <label className="flex items-center gap-1 cursor-pointer" title="按操作间隔自动插入等待节点">
          <Checkbox checked={autoWait} onCheckedChange={(c) => setAutoWait(c)} className="h-3.5 w-3.5" />
          <Clock className="w-3 h-3" />自动等待
        </label>
      </div>
    </div>,
    document.body,
    )}
    <ConfirmDialog />
    </>
  )
}
