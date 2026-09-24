import type { WorkflowPathSelection } from '../../../../shared/studio-platform'
import { checkedPathSelection } from './pathSelectionContract'

export async function nativePathSelection(request: WorkflowPathSelection) {
  try {
    const choose = window.autoflow?.chooseWorkflowPath
    if (!choose) return { success: false, error: '当前窗口没有原生路径选择能力' }
    const response = await choose(request)
    return checkedPathSelection(response.ok
      ? { success: true, data: { success: true, path: response.value.value ?? null } }
      : { success: false, error: response.error.message })
  } catch { return { success: false, error: '系统未能打开路径选择器' } }
}
