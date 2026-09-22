export type StudioLeaveRequest = {id:string; reason:'close'|'quit'|'workspace'|'restart'}
export type StudioOpenContext = {
  workspaceKey?: string
  instanceId?: string
  projectId?: string
  workflowId?: string
}
export type AutomationStudioBridge = {
  openAutomationStudio(context?: StudioOpenContext): Promise<void>
  onStudioTransitionEnd(handler:()=>void):()=>void
  onPrepareStudioLeave(handler:(request:StudioLeaveRequest)=>Promise<boolean>):()=>void
}
