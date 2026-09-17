import type { StreamingApiClient } from '../../shared/api/client'
import { createDataCommand, DataCommandUncertain, type DataCommandPolicy } from '../project-data/data-command'
import type { Automation, AutomationDirectoryQuery, AutomationPage, AutomationUpdate, AutomationValidation, AutomationWrite } from './types'

export { DataCommandUncertain as AutomationCommandUncertain } from '../project-data/data-command'
export type AutomationCommandPolicy = DataCommandPolicy
const encode = encodeURIComponent

/** Reuse the existing durable project-operation recovery protocol. */
export function createAutomationApi(client: StreamingApiClient, projectId: string) {
  const base = `/api/v1/projects/${encode(projectId)}/automations`
  const execute = createDataCommand(client, projectId)
  async function command(body: AutomationWrite | AutomationUpdate, key: string, automationId?: string, resume = false, policy?: DataCommandPolicy): Promise<Automation> {
    const workflowId = body.workflowId
    const result = await execute<Automation>(automationId ? `${base}/${encode(automationId)}` : base, automationId ? 'PUT' : 'POST', body, key, automationId ? 'updateAutomation' : 'createAutomation', resume, operation => {
      const { resource, result } = operation
      if (resource.type !== 'automation' || resource.projectId !== projectId || (automationId && resource.automationId !== automationId)
        || !result || !('automationId' in result) || result.automationId !== resource.automationId || result.projectId !== projectId || result.workflowId !== workflowId) {
        throw new Error('操作结果与当前自动化配置不一致')
      }
      return result
    }, policy)
    if ((policy?.canSubmit && !policy.canSubmit()) || result.projectId !== projectId || result.workflowId !== workflowId || (automationId && result.automationId !== automationId)) {
      throw new DataCommandUncertain(new Error('当前配置或工作区已变化，请在原上下文核对结果'))
    }
    return result
  }
  return {
    list: (query: AutomationDirectoryQuery, signal?: AbortSignal) => client.request<AutomationPage>(`${base}?q=${encode(query.query)}&page=${query.page}&pageSize=${query.pageSize}&sort=${encode(query.sort)}`, { signal }),
    get: (automationId: string, signal?: AbortSignal) => client.request<Automation>(`${base}/${encode(automationId)}`, { signal }),
    validation: (automationId: string, signal?: AbortSignal) => client.request<AutomationValidation>(`${base}/${encode(automationId)}/validation`, { signal }),
    create: (body: AutomationWrite, key: string, policy?: DataCommandPolicy) => command(body, key, undefined, false, policy),
    resumeCreate: (body: AutomationWrite, key: string, policy?: DataCommandPolicy) => command(body, key, undefined, true, policy),
    update: (automationId: string, body: AutomationUpdate, key: string, policy?: DataCommandPolicy) => command(body, key, automationId, false, policy),
    resumeUpdate: (automationId: string, body: AutomationUpdate, key: string, policy?: DataCommandPolicy) => command(body, key, automationId, true, policy),
  }
}
