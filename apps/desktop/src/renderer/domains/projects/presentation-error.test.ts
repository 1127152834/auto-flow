import { expect, it } from 'vitest'
import { safeProjectError } from './presentation-error'
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
