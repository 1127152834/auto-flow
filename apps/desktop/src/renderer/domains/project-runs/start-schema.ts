import type { components } from '../../shared/api/generated'

type Schema = components['schemas']
export type ParameterDefinition = Schema['ParameterDefinition']
export type EnvironmentPolicy = Schema['AutomationWrite']['environmentPolicy']
export type JsonScalar = string | number | boolean | null
export type ParameterDraftValue = JsonScalar | { raw: string }
export type BatchStartDraft = { parameters: Record<string, ParameterDraftValue>; maxTasks: string; unlimited?: boolean; concurrency?: string; environmentOverride?: EnvironmentPolicy }
export type BatchStartRequest = { expectedAutomationRevision: number; parameters: Record<string, JsonScalar>; maxTasks?: number | null; concurrency?: number; environmentOverride?: EnvironmentPolicy }
export type StartErrors = Record<string, string>

export function createBatchStartDraft(parameters: ParameterDefinition[], maxTasks = 1): BatchStartDraft {
  return { parameters: Object.fromEntries(parameters.filter(item => Object.hasOwn(item, 'defaultValue')).map(item => [item.parameterId, item.defaultValue!])), maxTasks: String(maxTasks) }
}

export function validateBatchStartDraft(draft: BatchStartDraft, definitions: ParameterDefinition[], options: { allowUnlimited?: boolean; dataBatch?: boolean } = {}): StartErrors {
  const errors: StartErrors = {}
  const knownIds = new Set(definitions.map(item => item.parameterId))
  for (const id of Object.keys(draft.parameters)) if (!knownIds.has(id)) errors[`parameters.${id}`] = '参数已不存在，请返回配置后重新确认'
  const count = Number(draft.maxTasks)
  if (!draft.unlimited && (!draft.maxTasks.trim() || !Number.isInteger(count) || count < 1 || count > 100)) errors.maxTasks = '本次任务数必须是 1–100 的整数'
  if (draft.unlimited && !options.allowUnlimited) errors.maxTasks = '不限次数需要至少一个必要数据输入'
  const concurrency = Number(draft.concurrency ?? '1')
  if (!(draft.concurrency ?? '1').trim() || !Number.isSafeInteger(concurrency) || concurrency < 1 || concurrency > 100) errors.concurrency = '请求并发数必须是 1–100 的整数'
  else if (!options.dataBatch && concurrency !== 1) errors.concurrency = '参数型自动化的并发数固定为 1'
  for (const item of definitions) {
    const present = Object.hasOwn(draft.parameters, item.parameterId)
    const draftValue = draft.parameters[item.parameterId]
    const value = item.type === 'number' && draftValue && typeof draftValue === 'object' ? Number(draftValue.raw) : draftValue
    if (item.required && !present) errors[`parameters.${item.parameterId}`] = '请填写必填参数'
    else if (item.type === 'number' && draftValue && typeof draftValue === 'object' && !draftValue.raw.trim()) errors[`parameters.${item.parameterId}`] = '请输入数字'
    else if (present && value !== null && typeof value !== item.type) errors[`parameters.${item.parameterId}`] = `请输入${item.type === 'number' ? '数字' : item.type === 'boolean' ? '布尔值' : '文本'}`
    else if (typeof value === 'number' && !Number.isFinite(value)) errors[`parameters.${item.parameterId}`] = '请输入有限数字'
  }
  return errors
}

export function toBatchStartRequest(draft: BatchStartDraft, definitions: ParameterDefinition[], expectedAutomationRevision: number, options: { allowUnlimited?: boolean; dataBatch?: boolean } = {}): BatchStartRequest | null {
  if (Object.keys(validateBatchStartDraft(draft, definitions, options)).length) return null
  const types = new Map(definitions.map(item => [item.parameterId, item.type]))
  const parameters = Object.fromEntries(Object.entries(draft.parameters).map(([id, value]) => [id, types.get(id) === 'number' && value && typeof value === 'object' ? Number(value.raw) : value])) as Record<string, JsonScalar>
  return { expectedAutomationRevision, parameters, maxTasks: draft.unlimited ? null : Number(draft.maxTasks), concurrency: Number(draft.concurrency ?? '1'), ...(draft.environmentOverride ? { environmentOverride: structuredClone(draft.environmentOverride) } : {}) }
}
