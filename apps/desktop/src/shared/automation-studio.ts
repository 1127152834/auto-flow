export type StudioLeaveReason = 'close' | 'quit' | 'workspace'

export type AutomationStudioBridge = {
  openAutomationStudio(): Promise<void>
  onPrepareStudioLeave(handler: (reason: StudioLeaveReason) => Promise<boolean>): () => void
  onStudioTransition(handler: (locked: boolean) => void): () => void
}
