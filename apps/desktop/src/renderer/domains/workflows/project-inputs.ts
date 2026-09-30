import { useWorkflowStore } from './editor-store'
import { create } from 'zustand'
import type { components } from '../../shared/api/generated'
import { ApiClientError, type ApiClient } from '../../shared/api/client'
import { createProjectRunsApi } from '../project-runs/api'
import { apiRequest } from './api'
import { getStudioOpenContext } from './api/config'
import { getStudioTransportRevision } from './api/transport'

type Schema = components['schemas']
export type ProjectAutomation = Schema['AutomationView']
export type DebugInputs = Schema['DebugInputResponse']
export type DebugSelection = DebugInputs['selection']
export type InputObject = { inputId: string; alias?: string; recordRef?: { recordKey: { value: string } }; values?: { fieldId: string; fieldName: string; value: unknown }[]; statusId?: string | null }
export const projectRequest: ApiClient['request'] = async <T,>(path: string, init?: Parameters<ApiClient['request']>[1]) => {
  const response = await apiRequest<T>(path.replace(/^\/api/, ''), { ...init, body: init?.body == null ? undefined : JSON.stringify(init.body) })
  if (!response.success || !response.data) throw new ApiClientError(response.error || '项目请求失败', response.httpStatus || 0, response.errorDetails || null)
  return response.data
}
export const projectRuns = (projectId: string) => createProjectRunsApi({ request: projectRequest }, projectId)
export const projectRoot = (projectId: string) => `/api/v1/projects/${encodeURIComponent(projectId)}`

interface ProjectInputState {
  automation: ProjectAutomation | null
  fields: Schema['DataFieldView'][]
  tables: Schema['DataTableView'][]
  statuses: Schema['DataStatusView'][]
  debug: DebugInputs | null
  task: Schema['TaskDetail'] | null
  taskDefinition: Pick<ProjectAutomation, 'inputPlan' | 'parameterSchema'> | null
  batchId: string | null
  busy: boolean
  error: string | null
  notice: string | null
  epoch: number
  load(): Promise<void>
  preview(choices?: DebugSelection): Promise<DebugInputs | null>
  candidates(inputId: string, cursor: string | null, search: string): Promise<DebugInputs>
  choose(inputId: string, choice: DebugSelection[string]): Promise<void>
}
export const useProjectInputs = create<ProjectInputState>((set, get) => ({
  automation: null, fields: [], tables: [], statuses: [], debug: null, task: null, taskDefinition: null, batchId: null, busy: false, error: null, notice: null, epoch: 0,
  async load() {
    const context = getStudioOpenContext(), epoch = get().epoch + 1, transport = getStudioTransportRevision()
    const previous = get()
    const keep = previous.automation?.automationId === context.automationId && previous.automation?.projectId === context.projectId
    set({ automation: keep ? previous.automation : null, fields: keep ? previous.fields : [], tables: keep ? previous.tables : [], statuses: keep ? previous.statuses : [], debug: null, task: keep ? previous.task : null, taskDefinition: keep ? previous.taskDefinition : null, batchId: null, busy: true, error: null, notice: null, epoch })
    const active = () => get().epoch === epoch && transport === getStudioTransportRevision()
    if (!context.projectId || !context.automationId) { set({ busy: false }); return }
    try {
      const automation = await projectRequest<ProjectAutomation>(`${projectRoot(context.projectId)}/automations/${encodeURIComponent(context.automationId)}`)
      if (automation.projectId !== context.projectId || automation.workflowId !== context.workflowId) throw new Error('自动化与工作流不匹配')
      const tables = [...new Set(automation.inputPlan.inputs.map(input => input.tableId))]
      const directories = await Promise.all(tables.map(async tableId => {
        const root = `${projectRoot(context.projectId!)}/tables/${encodeURIComponent(tableId)}`
        const [table, fields, statuses] = await Promise.all([projectRequest<Schema['DataTableView']>(root), projectRequest<Schema['DataFieldDirectory']>(`${root}/fields`), projectRequest<Schema['DataStatusDirectory']>(`${root}/statuses`)])
        return { table, fields: fields.items, statuses: statuses.items }
      }))
      if (active()) set({ automation, fields: directories.flatMap(item => item.fields), tables: directories.map(item => item.table), statuses: directories.flatMap(item => item.statuses), busy: false })
    } catch (error) { if (active()) set({ error: String(error), busy: false }); throw error }
  },
  async preview(choices = {}) {
    const { automation, epoch } = get(), transport = getStudioTransportRevision()
    if (!automation) return null
    set({ busy: true, error: null })
    try {
      const debug = await projectRequest<DebugInputs>(`${projectRoot(automation.projectId)}/automations/${automation.automationId}/debug-inputs`, { method: 'POST', body: { expectedAutomationRevision: automation.managementRevision, choices } })
      if (epoch !== get().epoch || transport !== getStudioTransportRevision()) return null
      set({ debug, busy: false })
      return debug
    } catch (error) { if (epoch === get().epoch) set({ busy: false, error: String(error) }); return null }
  },
  async candidates(inputId, cursor, search) {
    const { automation, debug } = get()
    if (!automation) throw new Error('未加载自动化')
    const choices = { ...debug?.selection }; delete choices[inputId]
    // Downstream choices must not incorrectly exclude another valid upstream candidate.
    for (const id of descendants(automation, inputId)) delete choices[id]
    return projectRequest<DebugInputs>(`${projectRoot(automation.projectId)}/automations/${automation.automationId}/debug-inputs`, { method: 'POST', body: { expectedAutomationRevision: automation.managementRevision, choices, inputId, cursor, search } })
  },
  async choose(inputId, choice) {
    const { automation, debug } = get()
    if (!automation) return
    const choices = { ...debug?.selection, [inputId]: choice }
    for (const id of descendants(automation, inputId)) delete choices[id]
    const next = await get().preview(choices)
    if (next && descendants(automation, inputId).size) set({ notice: '已按上游选择重新匹配关联对象；原关联选择已清除。' })
    if (next && next.selectionStatus !== 'ready') set({ error: '选择无法组成完整输入组，请检查关联对象或刷新数据' })
  },
}))

function descendants(automation: ProjectAutomation, id: string) {
  const ids = new Set([id])
  for (let pass = 0; pass < automation.inputPlan.inputs.length; pass++) for (const input of automation.inputPlan.inputs) if (input.relation && ids.has(input.relation.sourceInputId)) ids.add(input.inputId)
  ids.delete(id)
  return ids
}
export function inputReference(inputId: string, fieldId?: string) {
  return `PROJECT_INPUTS['${inputId}']${fieldId ? `['values']['${fieldId}']` : ''}`
}
export function projectReferences(automation: ProjectAutomation | null, fields: Schema['DataFieldView'][]) {
  if (!automation) return []
  return [
    ...automation.inputPlan.inputs.flatMap(input => input.fieldBindings.map(binding => ({ name: inputReference(input.inputId, binding.inputFieldId), label: `${input.alias} → ${binding.inputFieldAlias}`, type: fields.find(field => field.ref.fieldId === binding.fieldRef.fieldId)?.type ?? 'string', source: '项目数据' }))),
    ...automation.parameterSchema.map(parameter => ({ name: `PROJECT_PARAMETERS['${parameter.parameterId}']`, label: `固定参数 → ${parameter.name}`, type: parameter.type, source: '项目参数' })),
  ]
}

export function registerProjectReference(name: string) {
  const { automation, fields } = useProjectInputs.getState()
  const reference = projectReferences(automation, fields).find(item => item.name === name)
  const store = useWorkflowStore.getState(), node = store.nodes.find(item => item.id === store.selectedNodeId)
  if (reference && node) store.updateNodeData(node.id, { projectInputTypes: { ...(node.data.projectInputTypes as Record<string, string> ?? {}), [name]: reference.type } })
}

// Capture the type on the node that actually contains the expression, including pasted references.
export function captureProjectReferenceTypes() {
  const { automation, fields } = useProjectInputs.getState()
  const references = projectReferences(automation, fields)
  const store = useWorkflowStore.getState()
  for (const node of store.nodes) {
    const previous = (node.data.projectInputTypes ?? {}) as Record<string, string>
    const strings = (value: unknown): string[] => typeof value === 'string' ? [value.replace(/\["([^"]+)"\]/g, "['$1']")] : Array.isArray(value) ? value.flatMap(strings) : value && typeof value === 'object' ? Object.entries(value).filter(([key]) => key !== 'projectInputTypes').flatMap(([, child]) => strings(child)) : []
    const content = strings(node.data).join(' ')
    const next = { ...previous }
    for (const reference of references) if (content.includes(reference.name)) next[reference.name] ??= reference.type
    if (JSON.stringify(previous) !== JSON.stringify(next)) store.updateNodeData(node.id, { projectInputTypes: next })
  }
}
