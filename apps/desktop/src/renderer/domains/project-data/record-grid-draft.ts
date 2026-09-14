import type { components } from '../../shared/api/generated'
import { createRecordDraft, recordValues } from './record-draft'
import type { ScalarDraft } from './scalar-draft'

export type GridField = components['schemas']['DataFieldView']
export type GridCell = ScalarDraft & { inputError?: string }
export type GridDraftRow = { clientRowId: string; cells: Record<string, GridCell> }
export type GridError = { clientRowId: string; fieldId: string | null; message: string }
export type DraftHistory = { rows: GridDraftRow[]; past: GridDraftRow[][] }
export const MAX_GRID_ROWS = 100
export const MAX_GRID_BYTES = 1024 * 1024

export const draftHistory = (rows: GridDraftRow[] = []): DraftHistory => ({ rows, past: [] })
export const hasDraftValues = (rows: GridDraftRow[]) => rows.some(row => Object.values(row.cells).some(cell => cell.presence !== 'missing'))
export const newDraftRow = (fields: GridField[]): GridDraftRow => ({ clientRowId: crypto.randomUUID(), cells: createRecordDraft(fields) })
export const changeDraft = (state: DraftHistory, rows: GridDraftRow[]): DraftHistory => ({ rows, past: [...state.past, state.rows].slice(-50) })
export function addDraftRow(state: DraftHistory, fields: GridField[]): DraftHistory {
  if (state.rows.length >= MAX_GRID_ROWS) throw new Error('每次最多新增 100 行，更多数据请使用 Excel 导入')
  return changeDraft(state, [...state.rows, newDraftRow(fields)])
}
export const removeDraftRow = (state: DraftHistory, id: string) => changeDraft(state, state.rows.filter(row => row.clientRowId !== id))
export function updateDraftCell(state: DraftHistory, id: string, fieldId: string, cell: GridCell): DraftHistory {
  return changeDraft(state, state.rows.map(row => row.clientRowId === id ? { ...row, cells: { ...row.cells, [fieldId]: cell } } : row))
}
export function undoDraft(state: DraftHistory): DraftHistory {
  return state.past.length ? { rows: state.past[state.past.length - 1], past: state.past.slice(0, -1) } : state
}
export function gridValues(fields: GridField[], drafts: GridDraftRow[]) {
  const errors: GridError[] = []
  const rows = drafts.filter(row => hasDraftValues([row])).map(row => {
    const values: components['schemas']['DataCellWrite'][] = []
    for (const field of fields) {
      const fieldId = field.ref.fieldId
      try {
        const cell = row.cells[fieldId]
        if (cell?.inputError && cell.presence === 'value') throw new Error(cell.inputError)
        // Reuse the exact existing create validator, collecting all cells instead of stopping at the first.
        values.push(...recordValues([field], row.cells))
      } catch (error) {
        errors.push({ clientRowId: row.clientRowId, fieldId, message: error instanceof Error ? error.message : '字段值无效' })
      }
    }
    return { clientRowId: row.clientRowId, values }
  })
  return { rows: errors.length ? [] : rows, errors }
}
