import { useEffect, useRef, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { TableCell, TableRow } from '../../../shared/components/ui/table'
import { scalarDraft } from '../scalar-draft'
import type { GridCell, GridDraftRow, GridError, GridField } from '../record-grid-draft'
import { RecordGridCellEditor, type GridMove } from './RecordGridCellEditor'

export function RecordDraftRows({ rows, fields, errors, identityFieldId, selectionColumn = false, disabled, focusCell, onAdd, onRemove, onCellChange, onPaste, onSave, onUndo }: {
  rows: GridDraftRow[]; fields: GridField[]; errors: GridError[]; identityFieldId?: string; selectionColumn?: boolean; disabled?: boolean
  focusCell?: { rowId: string; fieldId: string; sequence: number }
  onAdd(focusFieldId?: string): void; onRemove(rowId: string): void; onCellChange(rowId: string, fieldId: string, value: GridCell): void
  onPaste(rowIndex: number, columnIndex: number, text: string): void; onSave(): void; onUndo(): void
}) {
  const [position, setPosition] = useState({ row: 0, column: 0 })
  const tail = useRef<HTMLTableRowElement>(null)
  const firstEditable = fields.findIndex(field => field.writable && !field.formula)
  const focus = (row: number, column: number) => {
    setPosition({ row, column })
    queueMicrotask(() => {
      const elements = tail.current?.parentElement?.querySelectorAll<HTMLElement>('[data-grid-cell]')
      const target = Array.from(elements ?? []).find(el => el.dataset.gridCell === `${row}:${fields[column]?.ref.fieldId}`)
      target?.focus(); target?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' })
    })
  }
  useEffect(() => {
    if (focusCell) {
      const row = rows.findIndex(r => r.clientRowId === focusCell.rowId), column = fields.findIndex(f => f.ref.fieldId === focusCell.fieldId)
      if (row >= 0 && column >= 0) focus(row, column)
    }
    // A focus request is an explicit sequence, not an effect of typing each character.
  }, [focusCell?.sequence])
  const move = (row: number, column: number, direction: GridMove) => {
    if (firstEditable < 0 || disabled) return
    let y = row, x = column
    if (direction === 'down' || direction === 'up') y += direction === 'down' ? 1 : -1
    else {
      const step = direction === 'next' ? 1 : -1
      do {
        x += step
        if (x >= fields.length) { y++; x = 0 }
        if (x < 0) { y--; x = fields.length - 1 }
      } while (y >= 0 && y <= rows.length && (!fields[x]?.writable || fields[x]?.formula))
    }
    if (y < 0) {
      tail.current?.closest('table')?.parentElement?.querySelector<HTMLElement>('button:not(:disabled)')?.focus()
      return
    }
    if (y === rows.length) {
      if (rows.length < 100) onAdd(fields[x]?.ref.fieldId)
      else document.querySelector<HTMLElement>('footer[aria-label="新增记录保存"] button:not(:disabled)')?.focus()
      return
    }
    if (y < rows.length) focus(y, x)
  }
  return <>
    {rows.map((row, index) => <TableRow role="row" key={row.clientRowId} data-record-draft={row.clientRowId} className="bg-clay-soft/40">
      {selectionColumn ? <TableCell aria-hidden /> : null}
      <TableCell className="text-sm text-muted">{identityFieldId ? row.cells[identityFieldId]?.text || '待填写身份字段' : '保存后生成'}</TableCell>
      {fields.map((field, column) => <TableCell role="presentation" className="af-table-draft-cell" key={field.ref.fieldId}>
        <RecordGridCellEditor field={field} rowNumber={index + 1} cell={row.cells[field.ref.fieldId] ?? scalarDraft(undefined)} disabled={disabled}
          active={position.row === index && position.column === column} error={errors.find(e => e.clientRowId === row.clientRowId && e.fieldId === field.ref.fieldId)?.message}
          onActivate={() => setPosition({ row: index, column })} onChange={value => onCellChange(row.clientRowId, field.ref.fieldId, value)}
          onMove={direction => move(index, column, direction)} onPasteGrid={text => onPaste(index, column, text)} onSave={onSave} onUndo={onUndo} />
      </TableCell>)}
      {!fields.length ? <TableCell /> : null}
      <TableCell className="text-sm text-muted">未设置</TableCell>
      <TableCell className="text-sm text-muted">未保存</TableCell>
      <TableCell><Button size="sm" variant="ghost" disabled={disabled} aria-label={`移除第 ${index + 1} 行草稿`} onClick={() => onRemove(row.clientRowId)}>移除</Button></TableCell>
    </TableRow>)}
    <TableRow ref={tail}><TableCell colSpan={Math.max(fields.length, 1) + 4 + Number(selectionColumn)}>
      <Button variant="ghost" disabled={disabled || rows.length >= 100 || firstEditable < 0} onClick={() => onAdd()}>＋ 点击新增一行</Button>
    </TableCell></TableRow>
  </>
}
