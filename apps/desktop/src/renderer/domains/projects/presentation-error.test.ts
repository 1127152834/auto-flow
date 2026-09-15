import { expect, it } from 'vitest'
import { safeProjectError } from './presentation-error'
import { ProjectCommandUncertain } from './api'
import { ApiClientError } from '../../shared/api/client'
const id = 'ab806c63-6b08-460b-bd2a-f3f6d2b07116'
it('maps known codes without echoing messages, details or request identities', () => {
  expect(safeProjectError(new ApiClientError(`record ${id} changed`, 409, 'REVISION_CONFLICT', { recordId: id }, id))).toBe('数据已更新，请读取最新内容后重试')
  expect(safeProjectError({ code: 'RESOURCE_UNAVAILABLE', message: id })).toBe('所需资源暂不可用，请检查配置')
})
it('never reflects arbitrary errors or string payloads', () => {
  for (const error of [new Error(id), { code: id, message: id }, id, null]) expect(safeProjectError(error)).toBe('操作失败，请重试')
})
it('presents data protection and external link failures without raw resource details', () => {
  expect(safeProjectError({ code: 'EXTERNAL_LINK_FAILED', message: id })).toBe('无法打开链接，请重试或复制链接')
  expect(safeProjectError({ code: 'STATUS_IN_USE', message: id })).toBe('仍有记录使用此状态，请先修改这些记录的业务状态')
  expect(safeProjectError({ code: 'FIELD_VALUES_INCOMPATIBLE', message: id })).toBe('现有记录不满足新的字段规则，请检查后重试')
})
it('presents the desktop export target conflict without exposing the selected path', () => {
  expect(safeProjectError({ code: 'OUTPUT_ALREADY_EXISTS', message: `/tmp/${id}.xlsx` })).toBe('目标文件已存在，请选择新的文件名')
})
it('keeps unknown operation results distinct from confirmed failures', () => {
  expect(safeProjectError({ code: 'OPERATION_RESULT_UNKNOWN', message: id })).toBe('运行结果尚未确认，请先核对原操作')
  expect(safeProjectError({ code: 'RUN_FACTS_INCOMPLETE', message: id })).toBe('运行资料暂不完整，请重新读取并核验')
  expect(safeProjectError({ code: 'RUN_ARTIFACT_UNAVAILABLE', message: id })).toBe('运行产物暂不可用，请刷新后重试')
})

it('preserves uncertain project saves as a recovery action without raw diagnostics', () => {
  expect(safeProjectError(new ProjectCommandUncertain(new Error(id)))).toBe('上次保存结果尚未确认，请核对保存结果')
})

it.each([
  ['PROFILE_REQUIRED', '请选择浏览器配置'],
  ['PROXY_UNAVAILABLE', '固定代理暂不可用，请检查代理配置'],
  ['PROXY_POOL_NOT_FOUND', '代理池暂不可用，请重新选择'],
  ['MODEL_PROVIDER_NOT_FOUND', '模型提供方暂不可用，请重新选择'],
  ['MODEL_PROVIDER_DISABLED', '模型提供方未启用，请检查配置'],
  ['WORKFLOW_UNAVAILABLE', '暂时无法检查工作流，请稍后重试'],
])('presents the actual automation validation code %s without resource identifiers', (code, message) => {
  expect(safeProjectError({ code, message: id, resource: { resourceId: id } })).toBe(message)
})
