import { StudioConnectionNotice } from '../domains/workflows/components/StudioConnectionNotice'
import { useEffect, type ReactNode } from 'react'
import { AIAssistantPanel } from '../domains/workflows/components/assistant/AIAssistantPanel'
import { useLayoutStore } from '../domains/workflows/hooks/stores/layoutStore'
import { useAIAssistantStore } from '../domains/workflows/hooks/stores/aiAssistantStore'
import { WorkflowEditor } from '../domains/workflows/components/WorkflowEditor'
import { InputPromptDialog } from '../domains/workflows/components/InputPromptDialog'
import { useStudioIntegration } from '../domains/workflows/hooks/useStudioIntegration'
import { useWorkflowStore } from '../domains/workflows/editor-store'

export function StudioApp({ tools }: { tools?: ReactNode }) {
  useStudioIntegration()
  const aiPanelOpen = useAIAssistantStore(state => state.isPanelOpen)
  const aiPanelWidth = useLayoutStore(state => state.aiAssistantWidth)
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (useWorkflowStore.getState().hasUnsavedChanges) { event.preventDefault(); event.returnValue = '' }
    }
    window.addEventListener('beforeunload', beforeUnload)
    return () => { window.removeEventListener('beforeunload', beforeUnload) }
  }, [])
  return <main aria-label="工作流工作台" className="studio-shell" style={{ paddingRight: aiPanelOpen ? aiPanelWidth : 0, transition: 'padding-right 200ms ease' }}>
    {tools}
    <StudioConnectionNotice />
    <div className="studio-editor @container"><WorkflowEditor /></div>
    <AIAssistantPanel /><InputPromptDialog />
  </main>
}
