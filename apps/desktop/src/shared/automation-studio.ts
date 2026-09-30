export type StudioLeaveRequest = {id:string; reason:'close'|'quit'|'workspace'|'restart'}
export type StudioOpenContext = {
  workspaceKey?: string
  instanceId?: string
  automationId?: string
  projectId?: string
  workflowId?: string
}
export type AutomationStudioBridge = {
  setStudioHotkeys(shortcuts: Record<string, string>): Promise<{success: boolean; count?: number; code?: string; error?: string}>
  onStudioHotkey(handler: (actionId: string) => void): () => void
  openAutomationStudio(context?: StudioOpenContext): Promise<void>
  onStudioTransitionEnd(handler:()=>void):()=>void
  onPrepareStudioLeave(handler:(request:StudioLeaveRequest)=>Promise<boolean>):()=>void
}
