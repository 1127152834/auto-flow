import type { AutomationWrite } from './types'

export type AutomationFormValues = AutomationWrite
export type AutomationFormErrors = Record<string, string>
const length = (value: string) => [...value].length

export function emptyAutomationForm(workflowId = ''): AutomationFormValues {
  return { name: '', description: '', workflowId, inputPlan: { inputs: [] }, parameterSchema: [], environmentPolicy: { source: 'newFromProfile' }, runPolicy: { maxTasks: 1, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 900, manualDeadlineSeconds: 900 } }
}

/** Explicit projection: never submit fetched capability facts or a stale revision as form fields. */
export function automationToForm(value: AutomationWrite): AutomationFormValues {
  const { name, description, workflowId, inputPlan, parameterSchema, environmentPolicy, runPolicy } = value
  return structuredClone({ name, description, workflowId, inputPlan, parameterSchema, environmentPolicy, runPolicy })
}

export function normalizeAutomation(value: AutomationFormValues): AutomationWrite {
  const result = automationToForm(value)
  result.name = result.name.trim()
  result.description = result.description.trim()
  result.parameterSchema = result.parameterSchema.map(item => ({ ...item, name: item.name.trim(), ...(item.description !== undefined ? { description: item.description.trim() } : {}) }))
  return result
}

export function validateAutomationForm(value: AutomationFormValues): AutomationFormErrors {
  const errors: AutomationFormErrors = {}
  if (!value.name.trim() || length(value.name.trim()) > 80) errors.name = '自动化名称需要 1–80 个字符'
  if (length(value.description.trim()) > 1000) errors.description = '用途说明最多 1000 个字符'
  value.parameterSchema.forEach((parameter, index, all) => {
    const prefix = `parameterSchema.${index}`
    if (parameter.description !== undefined && length(parameter.description.trim()) > 1000) errors[`${prefix}.description`] = '参数说明最多 1000 个字符'
    if (!parameter.name.trim()) errors[`${prefix}.name`] = '请输入参数名称'
    else if (all.some((other, otherIndex) => index !== otherIndex && other.name.trim() === parameter.name.trim())) errors[`${prefix}.name`] = '参数名称不能重复'
    if (Object.hasOwn(parameter, 'defaultValue') && parameter.defaultValue !== null && (typeof parameter.defaultValue !== parameter.type || (typeof parameter.defaultValue === 'number' && !Number.isFinite(parameter.defaultValue)))) errors[`${prefix}.defaultValue`] = '默认值必须符合参数类型'
  })
  const policy = value.runPolicy
  if (!Number.isInteger(policy.maxTasks) || policy.maxTasks < 1 || policy.maxTasks > 100) errors['runPolicy.maxTasks'] = '最大任务数必须是 1–100 的整数'
  for (const key of ['automaticExecutionTimeoutSeconds', 'manualDeadlineSeconds'] as const) if (!Number.isFinite(policy[key]) || policy[key] <= 0) errors[`runPolicy.${key}`] = '请输入有限的正数'
  for (const key of ['concurrency', 'maxLiveInstances'] as const) {
    if (value.inputPlan.inputs.length ? !Number.isInteger(policy[key]) || policy[key] < 1 || policy[key] > 100 : policy[key] !== 1) errors[`runPolicy.${key}`] = value.inputPlan.inputs.length ? '必须是 1–100 的整数' : '参数型自动化固定为 1'
  }
  const environment = value.environmentPolicy
  if (environment.source === 'newFromProfile' && Object.hasOwn(environment, 'profileId') && !environment.profileId) errors['environmentPolicy.profileId'] = '请选择浏览器配置'
  const proxy = environment.proxyOverride
  if (proxy?.mode === 'fixed' && !proxy.proxyId) errors['environmentPolicy.proxyOverride'] = '请选择固定代理'
  if (proxy?.mode === 'pool' && !proxy.proxyPoolId) errors['environmentPolicy.proxyOverride'] = '请选择代理池'
  return errors
}
