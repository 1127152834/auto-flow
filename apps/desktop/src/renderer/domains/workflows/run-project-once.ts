import type { components } from '../../shared/api/generated'
import { ApiClientError } from '../../shared/api/client'
import { useWorkflowStore } from './editor-store'
import { socketService } from './events'
import { getStudioOpenContext, getStudioResourceScope } from './api/config'
import { getStudioTransportRevision } from './api/transport'
import { advanceRunEvent, type RunEventCursor } from '../project-runs/events'
import { useNodeRunStore } from './hooks/stores/nodeRunStore'
import type { LogLevel } from './types'
import { projectRequest, projectRoot, projectRuns, useProjectInputs } from './project-inputs'

type Command = { key: string; body: components['schemas']['BatchStartRequest']; automationId: string; projectId: string; workflowId: string; batchId?: string }
const terminal = new Set(['completed', 'stopped', 'failed', 'interrupted'])
const storageKey = () => `autoflow:studio-debug:${JSON.stringify([getStudioResourceScope(), getStudioOpenContext().automationId])}`
let watching: Promise<void> | null = null
export const hasPendingProjectRun = () => Boolean(sessionStorage.getItem(storageKey()))

export async function runProjectOnce() {
  if (watching) return watching
  const state = useProjectInputs.getState(), context = getStudioOpenContext(), automation = state.automation
  if (!automation || context.automationId !== automation.automationId || context.workflowId !== automation.workflowId || automation.workflowId !== useWorkflowStore.getState().id) throw new Error('请从当前自动化打开专属工作流')
  const key = storageKey(), saved = sessionStorage.getItem(key)
  let command: Command
  if (saved) {
    command = JSON.parse(saved) as Command
    if (command.automationId !== automation.automationId || command.projectId !== automation.projectId || command.workflowId !== automation.workflowId || !command.key || command.body?.maxTasks !== 1 || command.body?.concurrency !== 1) throw new Error('原调试请求与当前自动化不匹配，请恢复原工作区核验')
  } else {
    const debug = state.debug ?? await state.preview()
    if (!debug || debug.selectionStatus !== 'ready') { useWorkflowStore.getState().setBottomPanelTab('project'); throw new Error('请先准备完整的调试输入') }
    command = { key: crypto.randomUUID(), body: { expectedAutomationRevision: automation.managementRevision, parameters: {}, maxTasks: 1, concurrency: 1, debugSelection: debug.selection }, automationId: automation.automationId, projectId: automation.projectId, workflowId: automation.workflowId }
    sessionStorage.setItem(key, JSON.stringify(command))
  }
  const transport = getStudioTransportRevision(), epoch = state.epoch
  const current = () => transport === getStudioTransportRevision() && epoch === useProjectInputs.getState().epoch && storageKey() === key
  const api = projectRuns(command.projectId)
  if (!command.batchId) {
    try {
      const outcome = await (saved ? api.resumeStart : api.start)(command.automationId, command.body, command.key, { canSubmit: current })
      const batchId = outcome.state === 'succeeded' ? outcome.batch.batchId : outcome.operation.resource.type === 'batch' ? outcome.operation.resource.batchId : null
      if (!batchId) throw new Error('启动结果没有返回批次身份')
      command.batchId = batchId
      sessionStorage.setItem(key, JSON.stringify(command))
    } catch (error) {
      if (error instanceof ApiClientError && error.status >= 400 && error.status < 500 && error.status !== 408) sessionStorage.removeItem(key)
      if (current()) useProjectInputs.setState({ error: String(error) })
      throw error
    }
  }
  if (!current()) return
  useProjectInputs.setState({ batchId: command.batchId, error: null, ...(state.task?.task.batchId !== command.batchId ? { task: null, taskDefinition: null } : {}) })
  watching = watchProjectTask(command.batchId!, command.projectId, command.workflowId).then(completed => {
    if (completed) sessionStorage.removeItem(key)
  }).catch(error => {
    if (current()) useProjectInputs.setState({ error: `运行状态核验中断：${String(error)}。请点击“核验本次运行”，不会再次创建任务。` })
    throw error
  }).finally(() => { watching = null })
  return watching
}

export async function stopProjectOnce() {
  const { automation, batchId } = useProjectInputs.getState()
  if (!automation || !batchId) return false
  const api = projectRuns(automation.projectId), batch = await api.getBatch(batchId)
  if (terminal.has(batch.batch.status)) return true
  await api.stop(batchId, { expectedStatusRevision: batch.batch.statusRevision, reason: 'Studio 停止单任务调试' }, crypto.randomUUID())
  return false // The monitor confirms terminal state; an accepted stop is not completion.
}

export async function watchProjectTask(batchId: string, projectId: string, workflowId: string) {
  const epoch = useProjectInputs.getState().epoch, transport = getStudioTransportRevision(), api = projectRuns(projectId)
  const current = () => epoch === useProjectInputs.getState().epoch && transport === getStudioTransportRevision() && workflowId === useWorkflowStore.getState().id
  useWorkflowStore.getState().setExecutionStatus('running')
  useWorkflowStore.getState().setBottomPanelTab('project')
  let boundRun: string | null = null
  let cursor: RunEventCursor | null = null
  while (current()) {
    const batch = await api.getBatch(batchId)
    if (!current()) return false
    const page = await api.listTasks({ batchId, page: 1, pageSize: 1, sort: '-createdAt' })
    if (!current()) return false
    if (page.items[0]) {
      const detail = await api.getTask(page.items[0].taskId)
      if (!current()) return false
      if (detail.task.batchId !== batchId || detail.task.runId !== detail.run.runId) throw new Error('任务身份不匹配')
      useProjectInputs.setState({ task: detail, taskDefinition: batch.configurationSnapshot.automation as unknown as ReturnType<typeof useProjectInputs.getState>['taskDefinition'] })
      if (boundRun !== detail.run.runId) {
        socketService.bindExecutionDocument(workflowId, workflowId, detail.run.runId)
        const store = useWorkflowStore.getState()
        store.setCurrentExecutionWorkflowId(workflowId)
        store.setCurrentExecutionRunId(detail.run.runId)
        store.clearLogs(); store.clearCollectedData(); useNodeRunStore.getState().clear()
        cursor = { runId: detail.run.runId, sequence: 0, terminal: false }
        boundRun = detail.run.runId
      }
      let eventPage: components['schemas']['ProjectRunEventPage']
      do {
        eventPage = await projectRequest<components['schemas']['ProjectRunEventPage']>(`${projectRoot(projectId)}/tasks/${encodeURIComponent(detail.task.taskId)}/events?afterSequence=${cursor!.sequence}`)
        if (!current()) return false
        for (const event of eventPage.items) {
          const next = advanceRunEvent(cursor!, event)
          if (next === cursor) continue
          const store = useWorkflowStore.getState()
          if (event.kind === 'log') store.addLogBatch([{ id: event.eventId, timestamp: event.occurredAt, origin: 'run', nodeId: event.nodeId ?? undefined, level: String(event.payload.level) as LogLevel, message: String(event.payload.message ?? '') }])
          if (event.kind === 'nodeAttempt' && event.nodeId) useNodeRunStore.getState().setStatus(event.nodeId, event.payload.status === 'started' ? 'running' : event.payload.status === 'succeeded' ? 'success' : 'failed')
          cursor = next
        }
        if (eventPage.afterSequence !== cursor!.sequence || eventPage.lastSequence < cursor!.sequence || eventPage.hasMore && !eventPage.items.length) throw new Error('运行事件补读结果不连续')
      } while (eventPage.hasMore)

    }
    // Wait for scheduler reconciliation, including release of all record leases.
    if (terminal.has(batch.batch.status)) {
      const task = useProjectInputs.getState().task
      useWorkflowStore.getState().setExecutionStatus(page.items.length && task?.task.batchId === batchId && task.task.status === 'succeeded' ? 'completed' : batch.batch.status === 'stopped' ? 'stopped' : 'failed')
      if (!page.items.length) useProjectInputs.setState({ error: String(batch.batch.selectionOutcome?.message ?? '未创建任务：所选数据不再符合条件或已被占用，请刷新') })
      return true
    }
    await new Promise(resolve => setTimeout(resolve, 750))
  }
  return false
}
