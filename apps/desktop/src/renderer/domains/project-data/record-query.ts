import type { components } from '../../shared/api/generated'
import { parseScalarDraft, scalarDraft, ScalarDraftError, type Scalar, type ScalarDraft, type ScalarDraftControl } from './scalar-draft'

export type FieldType = components['schemas']['DataFieldView']['type']
export type FilterExpression =
  | { type: 'all'; items: FilterExpression[] }
  | { type: 'any'; items: FilterExpression[] }
  | { type: 'not'; item: FilterExpression }
  | { type: 'compare'; fieldId: string; operator: string; value?: Scalar }
  | { type: 'status'; operator: string; statusId?: string }
export type OrderBy = { fieldId: string; direction: 'asc' | 'desc' } | { systemField: 'status' | 'createdAt' | 'updatedAt' | 'recordKey'; direction: 'asc' | 'desc' }
export type RecordQuery = { filter: FilterExpression; orderBy: OrderBy[] }
export type FilterDraft =
  | { type: 'all'; items: FilterDraft[] }
  | { type: 'any'; items: FilterDraft[] }
  | { type: 'not'; item: FilterDraft }
  | { type: 'compare'; fieldId: string; operator: string; value: ScalarDraft }
  | { type: 'status'; operator: string; statusId: string }
export type RecordQueryDraft = { filter: FilterDraft; orderBy: OrderBy[] }

export class RecordQueryError extends Error {
  constructor(readonly path: string, message: string, readonly control?: ScalarDraftControl) { super(message); this.name = 'RecordQueryError' }
}

export const emptyRecordQuery = (): RecordQuery => ({ filter: { type: 'all', items: [] }, orderBy: [] })

function draftFilter(filter: FilterExpression): FilterDraft {
  if (filter.type === 'all') return { type: 'all', items: filter.items.map(draftFilter) }
  if (filter.type === 'any') return { type: 'any', items: filter.items.map(draftFilter) }
  if (filter.type === 'not') return { type: 'not', item: draftFilter(filter.item) }
  if (filter.type === 'status') return { type: 'status', operator: filter.operator, statusId: filter.statusId ?? '' }
  return { type: 'compare', fieldId: filter.fieldId, operator: filter.operator, value: scalarDraft(filter.value) }
}

export function recordQueryDraft(value: RecordQuery = emptyRecordQuery()): RecordQueryDraft {
  return { filter: draftFilter(value.filter), orderBy: structuredClone(value.orderBy) }
}

const operations: Record<FieldType, Set<string>> = {
  string: new Set(['eq', 'neq', 'contains', 'startsWith', 'isNull', 'isNotNull']),
  number: new Set(['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'isNull', 'isNotNull']),
  boolean: new Set(['eq', 'neq', 'isNull', 'isNotNull']),
  date: new Set(['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'isNull', 'isNotNull']),
}
export const operatorsFor = (type: FieldType) => [...operations[type]]
const nullOperator = (value: string) => value === 'isNull' || value === 'isNotNull'

export function parseRecordQuery(draft: RecordQueryDraft, fields: readonly { ref: { fieldId: string }; type: FieldType }[], statuses: readonly { statusId: string }[]): RecordQuery {
  const fieldTypes = new Map(fields.map(field => [field.ref.fieldId, field.type]))
  const statusIds = new Set(statuses.map(status => status.statusId))
  let leaves = 0
  const walk = (node: FilterDraft, depth: number, path: string): FilterExpression => {
    if (depth > 5) throw new RecordQueryError(path, '筛选嵌套最多 5 层')
    if (node.type === 'all' || node.type === 'any') {
      if (node.items.length > 50) throw new RecordQueryError(path, '每个条件组最多 50 项')
      if (node.type === 'any' && node.items.length === 0) throw new RecordQueryError(path, '“任一”条件组不能为空')
      return { type: node.type, items: node.items.map((item, index) => walk(item, depth + 1, `${path}.items.${index}`)) }
    }
    if (node.type === 'not') return { type: 'not', item: walk(node.item, depth + 1, `${path}.item`) }
    leaves += 1
    if (leaves > 100) throw new RecordQueryError(path, '筛选条件最多 100 项')
    if (node.type === 'status') {
      if (!['eq', 'neq', 'isNull', 'isNotNull'].includes(node.operator)) throw new RecordQueryError(path, '状态运算符无效')
      if (nullOperator(node.operator)) return { type: 'status', operator: node.operator }
      if (!statusIds.has(node.statusId)) throw new RecordQueryError(path, '所选状态已失效')
      return { type: 'status', operator: node.operator, statusId: node.statusId }
    }
    const type = fieldTypes.get(node.fieldId)
    if (!type) throw new RecordQueryError(path, '所选字段已失效')
    if (!operations[type].has(node.operator)) throw new RecordQueryError(path, '运算符不适用于该字段')
    if (nullOperator(node.operator)) return { type: 'compare', fieldId: node.fieldId, operator: node.operator }
    let value: Scalar | undefined
    try { value = parseScalarDraft(type, node.value) } catch (error) {
      if (error instanceof ScalarDraftError) throw new RecordQueryError(path, error.message, error.control)
      throw error
    }
    if (value === undefined || value === null) throw new RecordQueryError(path, '比较值不能为空', 'presence')
    return { type: 'compare', fieldId: node.fieldId, operator: node.operator, value }
  }
  if (draft.orderBy.length > 8) throw new RecordQueryError('orderBy', '排序最多 8 项')
  const seen = new Set<string>()
  for (const [index, order] of draft.orderBy.entries()) {
    const target = 'fieldId' in order ? `field:${order.fieldId}` : `system:${order.systemField}`
    if (seen.has(target)) throw new RecordQueryError(`orderBy.${index}`, '排序字段不能重复')
    seen.add(target)
    if ('fieldId' in order && !fieldTypes.has(order.fieldId)) throw new RecordQueryError(`orderBy.${index}`, '排序字段已失效')
  }
  const filter = walk(draft.filter, 1, 'filter'), orderBy = structuredClone(draft.orderBy)
  const encodedLength = (value: unknown) => Math.ceil(new TextEncoder().encode(JSON.stringify(value)).length * 4 / 3)
  if (encodedLength(filter) > 65_536) throw new RecordQueryError('filter', '筛选条件超过 64 KiB')
  if (encodedLength(orderBy) > 65_536) throw new RecordQueryError('orderBy', '排序条件超过 64 KiB')
  return { filter, orderBy }
}
