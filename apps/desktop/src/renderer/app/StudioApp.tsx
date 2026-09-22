import {hasSettingsCloseHandler,requestSettingsClose} from '../domains/workflows/lib/settingsLeave'
import {requestDocumentLeave,getDocumentLeaveResources} from '../domains/workflows/lib/documentLeave'
import { StudioConnectionNotice } from '../domains/workflows/components/StudioConnectionNotice'
import { useEffect,useRef,useState, type ReactNode } from 'react'
import { AIAssistantPanel } from '../domains/workflows/components/assistant/AIAssistantPanel'
import { useLayoutStore } from '../domains/workflows/hooks/stores/layoutStore'
import { useAIAssistantStore } from '../domains/workflows/hooks/stores/aiAssistantStore'
import { WorkflowEditor } from '../domains/workflows/components/WorkflowEditor'
import { InputPromptDialog } from '../domains/workflows/components/InputPromptDialog'
import { useStudioIntegration } from '../domains/workflows/hooks/useStudioIntegration'
import { useWorkflowStore } from '../domains/workflows/editor-store'
import { workflowApi } from '../domains/workflows/api'
import { getStudioOpenContext } from '../domains/workflows/api/config'

export function StudioApp({ tools }: { tools?: ReactNode }) {
  useStudioIntegration()
  const [contextError, setContextError] = useState<string | null>(null)
  const context = getStudioOpenContext()
  const loadedWorkflow = useRef<string | null>(null)
  useEffect(() => {
    if (!context.workflowId || loadedWorkflow.current === context.workflowId) return
    let disposed = false
    const load = async () => {
      const result = await workflowApi.get(context.workflowId!)
      if (disposed) return
      if (!result.success || !result.data || !useWorkflowStore.getState().importWorkflow(result.data)) {
        setContextError(result.error || '无法读取项目工作流')
        return
      }
      loadedWorkflow.current = context.workflowId!
      setContextError(null)
    }
    void load()
    const retry = () => { if (!loadedWorkflow.current) void load() }
    window.addEventListener('studio:transport-changed', retry)
    return () => { disposed = true; window.removeEventListener('studio:transport-changed', retry) }
  }, [context.workflowId])
  const transitioningRef=useRef(false)
  const [transitioning,setTransitioning]=useState(false)
  useEffect(()=>{
    const stop=window.autoflow?.onPrepareStudioLeave?.(async request=>{
      if(request.reason==='restart')return getDocumentLeaveResources().length===0
      if(hasSettingsCloseHandler()&&!await requestSettingsClose())return false
      const allowed=await requestDocumentLeave()
      if(allowed&&request.reason==='workspace'){transitioningRef.current=true;setTransitioning(true)}
      return allowed
    })
    const finish=window.autoflow?.onStudioTransitionEnd?.(()=>{transitioningRef.current=false;setTransitioning(false)})
    const block=(event:Event)=>{if(transitioningRef.current){event.preventDefault();event.stopImmediatePropagation()}}
    const events=['keydown','pointerdown','click','input','change']
    for(const event of events)window.addEventListener(event,block,true)
    return()=>{stop?.();finish?.();for(const event of events)window.removeEventListener(event,block,true)}
  },[])
  const aiPanelOpen = useAIAssistantStore(state => state.isPanelOpen)
  const aiPanelWidth = useLayoutStore(state => state.aiAssistantWidth)
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (useWorkflowStore.getState().hasUnsavedChanges||getDocumentLeaveResources().length) { event.preventDefault(); event.returnValue = '' }
    }
    window.addEventListener('beforeunload', beforeUnload)
    return () => { window.removeEventListener('beforeunload', beforeUnload) }
  }, [])
  return <main aria-label="工作流工作台" className="studio-shell" style={{ paddingRight: aiPanelOpen ? aiPanelWidth : 0, transition: 'padding-right 200ms ease' }}>
    {transitioning&&<div role="status" className="fixed inset-0 z-[9999] bg-[hsl(var(--background)/0.9)] grid place-items-center">正在切换工作区，编辑暂时锁定…</div>}
    {tools}
    <StudioConnectionNotice />
    {contextError ? <div role="alert" className="mx-4 mt-3 rounded-control border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">{contextError}</div> : null}
    <div className="studio-editor @container"><WorkflowEditor /></div>
    <AIAssistantPanel /><InputPromptDialog />
  </main>
}
