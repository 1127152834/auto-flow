export type StudioLeaveRequest = {id:string; reason:'close'|'quit'|'workspace'|'restart'}
export type AutomationStudioBridge = {
  openAutomationStudio(): Promise<void>
  onStudioTransitionEnd(handler:()=>void):()=>void
  onPrepareStudioLeave(handler:(request:StudioLeaveRequest)=>Promise<boolean>):()=>void
}
