import { useWorkflowStore } from '../editor-store'
import { useCustomModuleStore } from '../hooks/stores/customModuleStore'
import { customModulesApi } from '../api'
import { requestDocumentLeave } from './documentLeave'
import { snapshotKey } from './snapshotKey'

const backupKey = 'preEditWorkflowBackup'
let entering = false
let saving = false

function report(message: string) {
  useWorkflowStore.getState().addLog({ level: 'error', message })
}

export async function enterCustomModuleEditing(id: string): Promise<boolean> {
  if (entering) return false
  if (sessionStorage.getItem('editingCustomModuleId') === id && sessionStorage.getItem('editingCustomModuleDocumentId') === useWorkflowStore.getState().id) return true
  entering = true
  try {
    const original = snapshotKey(useWorkflowStore.getState().exportWorkflow())
    const latest = await useCustomModuleStore.getState().getModule(id)
    if (!latest) throw new Error('无法读取最新模块，请重试；当前画布已保留')
    if (snapshotKey(useWorkflowStore.getState().exportWorkflow()) !== original) throw new Error('读取模块期间草稿已变化，请重新打开')
    if (sessionStorage.getItem('editingCustomModuleId') && !(await requestDocumentLeave({ preserveMainDocument: true }))) return false
    const state = useWorkflowStore.getState()
    const alreadyEditing = !!sessionStorage.getItem('editingCustomModuleId')
    if (!alreadyEditing) {
      const { id: documentId, name, browserEnvironmentVersion, nodes, edges, variables, history, historyIndex, hasUnsavedChanges, selectedNodeId } = state
      sessionStorage.setItem(backupKey, JSON.stringify({ id: documentId, name, browserEnvironmentVersion, nodes, edges, variables, history, historyIndex, hasUnsavedChanges, selectedNodeId }))
    }
    const previousId = sessionStorage.getItem('editingCustomModuleId')
    const previousName = sessionStorage.getItem('editingCustomModuleName')
    const previousDocumentId = sessionStorage.getItem('editingCustomModuleDocumentId')
    const documentId = crypto.randomUUID()
    try {
      sessionStorage.setItem('editingCustomModuleId', latest.id)
      sessionStorage.setItem('editingCustomModuleName', latest.display_name || latest.name)
      sessionStorage.setItem('editingCustomModuleDocumentId', documentId)
      if (!state.importWorkflow({ ...latest.workflow, id: documentId, name: `编辑模块: ${latest.display_name || latest.name}` })) throw new Error('模块工作流格式损坏，当前画布已保留')
    } catch (error) {
      if (previousId) sessionStorage.setItem('editingCustomModuleId', previousId)
      else sessionStorage.removeItem('editingCustomModuleId')
      if (previousName) sessionStorage.setItem('editingCustomModuleName', previousName)
      else sessionStorage.removeItem('editingCustomModuleName')
      if (previousDocumentId) sessionStorage.setItem('editingCustomModuleDocumentId', previousDocumentId)
      else sessionStorage.removeItem('editingCustomModuleDocumentId')
      if (!alreadyEditing) sessionStorage.removeItem(backupKey)
      throw error
    }
    window.dispatchEvent(new CustomEvent('editingModuleChanged'))
    return true
  } catch (error) { report(String(error)); return false }
  finally { entering = false }
}

export async function saveCustomModuleEditing(): Promise<boolean> {
  const id = sessionStorage.getItem('editingCustomModuleId')
  if (!id || saving) return false
  if (sessionStorage.getItem('editingCustomModuleDocumentId') !== useWorkflowStore.getState().id) {
    report('模块画布尚未恢复，不能保存空白或其他文档；请重新打开模块')
    return false
  }
  saving = true
  try {
    const serialized = useWorkflowStore.getState().exportWorkflow()
    const { nodes, edges, variables, schemaVersion, browserEnvironmentVersion } = JSON.parse(serialized)
    const result = await customModulesApi.update(id, { workflow: { nodes, edges, variables, schemaVersion, browserEnvironmentVersion } })
    if (!result.success || result.error || result.data?.success === false || result.data?.id !== id) throw new Error(result.error || result.data?.error || '模块保存未得到确认')
    useCustomModuleStore.setState(state => ({ modules: state.modules.map(module => module.id === id ? result.data : module) }))
    if (sessionStorage.getItem('editingCustomModuleId') !== id || snapshotKey(useWorkflowStore.getState().exportWorkflow()) !== snapshotKey(serialized)) {
      report('模块已保存，但期间草稿已变化；新修改仍未保存')
      return false
    }
    useWorkflowStore.getState().markAsSaved()
    useWorkflowStore.getState().addLog({ level: 'success', message: '模块工作流已保存' })
    return true
  } catch (error) { report(`模块保存失败: ${String(error)}`); return false }
  finally { saving = false }
}

/** Called only after the mounted editor has resolved the module's draft decision. */
export function restoreMainWorkflow(): boolean {
  try {
    const raw = sessionStorage.getItem(backupKey)
    if (!raw) throw new Error('主工作流备份缺失；已保留模块草稿，请先导出备份')
    const backup = JSON.parse(raw)
    if (!Array.isArray(backup.nodes) || !Array.isArray(backup.edges) || !Array.isArray(backup.variables) || typeof backup.name !== 'string') throw new Error('主工作流备份损坏；已保留模块草稿')
    if (backup.id && (!Array.isArray(backup.history) || !Number.isInteger(backup.historyIndex) || !backup.history[backup.historyIndex])) throw new Error('主工作流历史备份损坏；已保留模块草稿')
    if (backup.id) {
      const { id, nodes, edges, variables, name, browserEnvironmentVersion, history, historyIndex, hasUnsavedChanges, selectedNodeId } = backup
      useWorkflowStore.setState({ id, nodes, edges, variables, name, browserEnvironmentVersion, history, historyIndex, hasUnsavedChanges, selectedNodeId })
    } else {
      // Legacy backups did not retain document identity or history.
      useWorkflowStore.getState().restoreSnapshot(backup, { resetHistory: true })
    }
    sessionStorage.removeItem('editingCustomModuleId')
    sessionStorage.removeItem('editingCustomModuleName')
    sessionStorage.removeItem('editingCustomModuleDocumentId')
    sessionStorage.removeItem(backupKey)
    window.dispatchEvent(new CustomEvent('editingModuleChanged'))
    useWorkflowStore.getState().addLog({ level: 'info', message: '已退出模块编辑，主工作流已恢复' })
    return true
  } catch (error) { report(String(error)); return false }
}

/** A refresh may retain sessionStorage while losing the in-memory canvas. */
export async function recoverCustomModuleEditing(): Promise<boolean> {
  const id = sessionStorage.getItem('editingCustomModuleId')
  if (!id || sessionStorage.getItem('editingCustomModuleDocumentId') === useWorkflowStore.getState().id) return true
  return enterCustomModuleEditing(id)
}
