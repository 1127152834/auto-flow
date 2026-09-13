import {useWorkflowStore} from '../editor-store'

type Heal = {nodeId?: string; configKey?: string; oldSelector?: string; newSelector?: string}
type Detail = {workflowId?: string; documentId?: string; heals?: Heal[]}

/** Review a runtime suggestion against the draft it actually describes. Never auto-save. */
export async function reviewSelectorHeals(detail: Detail, confirm: (message: string) => Promise<boolean>, isCurrent = () => true) {
  const original = useWorkflowStore.getState()
  if (!detail || detail.documentId !== original.id || !Array.isArray(detail.heals) || !detail.heals.length) return
  const updates: {nodeId: string; data: Record<string, string>; oldSelector: string; key: string}[] = []
  const seen = new Set<string>()
  for (const heal of detail.heals) {
    if (!heal || typeof heal !== 'object') return
    const key = heal.configKey || 'selector'
    if (typeof heal.nodeId !== 'string' || typeof heal.oldSelector !== 'string' ||
        typeof heal.newSelector !== 'string' || !heal.newSelector.trim() ||
        typeof key !== 'string' || ['__proto__', 'constructor', 'prototype'].includes(key)) return
    const identity = JSON.stringify([heal.nodeId, key])
    if (seen.has(identity)) return
    seen.add(identity)
    const node = original.nodes.find(node => node.id === heal.nodeId)
    if (!node || node.data[key] !== heal.oldSelector) return
    updates.push({nodeId: heal.nodeId, data: {[key]: heal.newSelector}, oldSelector: heal.oldSelector, key})
  }
  if (!await confirm(`本次运行有 ${updates.length} 处选择器失效后被自动修复。是否把修复后的选择器写入当前草稿？写入后仍需手动保存。`)) return
  const store = useWorkflowStore.getState()
  if (!isCurrent() || store.id !== original.id) return
  if (updates.some(update => store.nodes.find(node => node.id === update.nodeId)?.data[update.key] !== update.oldSelector)) {
    store.addLog({level: 'warning', message: '选择器修复建议已过期，节点或字段已修改，未写回草稿'})
    return
  }
  store.updateNodesData(updates.map(({nodeId, data}) => ({nodeId, data})))
  store.addLog({level: 'success', message: `已写回 ${updates.length} 处自愈选择器，记得保存工作流`})
}
