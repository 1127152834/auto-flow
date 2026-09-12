import { signature } from './editor-model'
import type { WorkflowContent } from './types'

export type WorkflowHistory = { past: WorkflowContent[]; present: WorkflowContent; future: WorkflowContent[] }
export function createHistory(content: WorkflowContent): WorkflowHistory { return { past: [], present: content, future: [] } }
export function editHistory(history: WorkflowHistory, next: WorkflowContent, grouped = false): WorkflowHistory {
  if (signature(history.present) === signature(next)) return { ...history, present: next }
  // ponytail: bounded document snapshots; replace with commands if large workflows make 100 snapshots costly.
  return { past: grouped ? history.past : [...history.past, history.present].slice(-100), present: next, future: [] }
}
function withCamera(target: WorkflowContent, current: WorkflowContent): WorkflowContent { return { ...target, layout: { ...target.layout, viewport: current.layout.viewport } } }
export function undoHistory(history: WorkflowHistory): WorkflowHistory {
  const previous = history.past.at(-1)
  return previous ? { past: history.past.slice(0, -1), present: withCamera(previous, history.present), future: [history.present, ...history.future] } : history
}
export function redoHistory(history: WorkflowHistory): WorkflowHistory {
  const next = history.future[0]
  return next ? { past: [...history.past, history.present], present: withCamera(next, history.present), future: history.future.slice(1) } : history
}
