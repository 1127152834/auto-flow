import { changeDraft, MAX_GRID_BYTES, MAX_GRID_ROWS, newDraftRow, type DraftHistory, type GridCell, type GridField } from './record-grid-draft'
import { scalarDraft } from './scalar-draft'

type Token = { text: string; quoted: boolean }
export function parseGridClipboard(text: string): Token[][] {
  if (new TextEncoder().encode(text).length > MAX_GRID_BYTES) throw new Error('粘贴内容超过 1 MiB，请使用 Excel 导入')
  const rows: Token[][] = [[]]
  let value = '', quoted = false, inQuotes = false, closed = false, start = true
  const emit = () => { rows[rows.length - 1].push({ text: value, quoted }); value = ''; quoted = false; closed = false; start = true }
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (inQuotes) {
      if (c === '"' && text[i + 1] === '"') { value += '"'; i++ }
      else if (c === '"') { inQuotes = false; closed = true }
      else value += c
    } else if (c === '\t' || c === '\r' || c === '\n') {
      emit()
      if (c !== '\t') {
        if (c === '\r' && text[i + 1] === '\n') i++
        rows.push([])
        if (rows.length > MAX_GRID_ROWS + 1) throw new Error('每次最多粘贴 100 行')
      }
    } else if (c === '"' && start) { quoted = true; inQuotes = true; start = false }
    else {
      if (closed) throw new Error('粘贴内容的引号格式无效')
      value += c; start = false
    }
  }
  if (inQuotes) throw new Error('粘贴内容的引号未闭合')
  if (rows[rows.length - 1].length || value || quoted || !/[\r\n]$/.test(text)) emit()
  else rows.pop()
  if (rows.length > MAX_GRID_ROWS) throw new Error('每次最多粘贴 100 行')
  return rows
}
function cellFromToken(field: GridField, token: Token): GridCell {
  if (!token.text && !token.quoted) return scalarDraft(undefined)
  const cell: GridCell = { ...scalarDraft(token.text), text: token.text }
  if (field.type === 'boolean') {
    if (/^(true|false)$/i.test(token.text)) cell.boolean = token.text.toLowerCase() === 'true'
    else cell.inputError = '布尔值请输入 true 或 false'
  }
  if (token.quoted && !token.text && field.type !== 'string') cell.inputError = '空文本仅适用于文本字段'
  if (field.type === 'date' && token.text.includes('T')) {
    const match = /^(.*T\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:\d{2})?$/.exec(token.text)
    cell.precision = 'datetime'
    if (match) { cell.text = match[1]; cell.offset = match[2] ?? '' }
  }
  return cell
}
export function pasteGridCells(state: DraftHistory, fields: GridField[], columns: GridField[], rowIndex: number, columnIndex: number, text: string): DraftHistory {
  const matrix = parseGridClipboard(text)
  if (rowIndex < 0 || columnIndex < 0 || rowIndex >= state.rows.length || rowIndex + matrix.length > MAX_GRID_ROWS) throw new Error('粘贴位置无效或超过 100 行')
  for (const row of matrix) {
    if (columnIndex + row.length > columns.length) throw new Error('粘贴列数超过可用列，原输入未改变')
    for (let index = 0; index < row.length; index++) {
      const field = columns[columnIndex + index]
      if (!field.writable || field.formula || !fields.some(f => f.ref.fieldId === field.ref.fieldId)) throw new Error('不能粘贴到只读列')
    }
  }
  const rows = state.rows.map(row => ({ ...row, cells: { ...row.cells } }))
  while (rows.length < rowIndex + matrix.length) rows.push(newDraftRow(fields))
  matrix.forEach((row, y) => row.forEach((token, x) => {
    const field = columns[columnIndex + x]
    rows[rowIndex + y].cells[field.ref.fieldId] = cellFromToken(field, token)
  }))
  return changeDraft(state, rows)
}
