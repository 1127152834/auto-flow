// Form-side helpers for project_data write-back nodes: turn rows into the stored argument shapes and back.

export interface FieldRow { fieldId: string; value: unknown }
export interface Condition { fieldId: string; operator: string; value?: unknown }

const isRecord = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)

export const valueText = (value: unknown): string => typeof value === 'string' ? value : value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value)

/** Typed text becomes a number or boolean only when the field asks for it and the text is a plain literal; references stay text. */
export function coerceValue(type: string | undefined, text: string): unknown {
  if (type === 'number' && text.trim() !== '' && Number.isFinite(Number(text))) return Number(text)
  if (type === 'boolean' && (text === 'true' || text === 'false')) return text === 'true'
  return text
}

export const rowsFromRecord = (record: unknown): FieldRow[] => isRecord(record) ? Object.entries(record).map(([fieldId, value]) => ({ fieldId, value })) : []
export const recordFromRows = (rows: FieldRow[]): Record<string, unknown> => Object.fromEntries(rows.filter(row => row.fieldId).map(row => [row.fieldId, row.value]))

/** Reads a stored filter as flat conditions; null means it is more complex than the form can show and must be left alone. */
export function conditionsFromFilter(filter: unknown): Condition[] | null {
  if (filter == null) return []
  if (!isRecord(filter) || filter.type !== 'all' || !Array.isArray(filter.items)) return null
  const result: Condition[] = []
  for (const item of filter.items) {
    if (!isRecord(item) || item.type !== 'compare' || typeof item.fieldId !== 'string' || typeof item.operator !== 'string') return null
    result.push({ fieldId: item.fieldId, operator: item.operator, ...('value' in item ? { value: item.value } : {}) })
  }
  return result
}

export const isNullOperator = (operator: string) => operator === 'isNull' || operator === 'isNotNull'

export function filterFromConditions(conditions: Condition[]): Record<string, unknown> | null {
  const items = conditions.filter(item => item.fieldId).map(item => ({ type: 'compare', fieldId: item.fieldId, operator: item.operator, ...(isNullOperator(item.operator) ? {} : { value: item.value ?? '' }) }))
  return items.length ? { type: 'all', items } : null
}
