import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { RecordGridCellEditor } from './RecordGridCellEditor'
import { scalarDraft } from '../scalar-draft'
afterEach(cleanup)
const field = { ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId: 'f' }, key: 'title', name: '标题', type: 'string' as const, required: true, validation: {}, writable: true, formula: false, fieldRevision: 1 }
it('edits inside a cell and Escape restores only the current edit', () => {
 const onChange = vi.fn(), onMove = vi.fn()
 render(<RecordGridCellEditor field={field} rowNumber={1} cell={scalarDraft('old')} active onActivate={vi.fn()} onChange={onChange} onMove={onMove} onPasteGrid={vi.fn()} onSave={vi.fn()} onUndo={vi.fn()} />)
 const cell = screen.getByRole('gridcell')
 fireEvent.doubleClick(cell)
 const input = screen.getByRole('textbox', { name: '第 1 行 · 标题' })
 fireEvent.change(input, { target: { value: 'new' } })
 fireEvent.keyDown(input, { key: 'Escape' })
 expect(onChange).toHaveBeenLastCalledWith(scalarDraft('old'))
 expect(onMove).not.toHaveBeenCalled()
 expect(screen.queryByRole('dialog')).toBeNull()
})
it('does not navigate or save while the Chinese IME is composing', () => {
 const onMove = vi.fn(), onSave = vi.fn()
 render(<RecordGridCellEditor field={field} rowNumber={1} cell={scalarDraft('')} active onActivate={vi.fn()} onChange={vi.fn()} onMove={onMove} onPasteGrid={vi.fn()} onSave={onSave} onUndo={vi.fn()} />)
 fireEvent.doubleClick(screen.getByRole('gridcell'))
 fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter', isComposing: true })
 expect(onMove).not.toHaveBeenCalled(); expect(onSave).not.toHaveBeenCalled()
})
it('exposes the field error and leaves clipboard handling to grid selection mode', () => {
 const onPasteGrid = vi.fn()
 render(<RecordGridCellEditor field={field} rowNumber={3} cell={scalarDraft(undefined)} active error="请填写必填字段" onActivate={vi.fn()} onChange={vi.fn()} onMove={vi.fn()} onPasteGrid={onPasteGrid} onSave={vi.fn()} onUndo={vi.fn()} />)
 const cell = screen.getByRole('gridcell')
 expect(cell.getAttribute('aria-invalid')).toBe('true')
 fireEvent.paste(cell, { clipboardData: { getData: () => 'a\tb' } })
 expect(onPasteGrid).toHaveBeenCalledWith('a\tb')
})
it('keeps the entered value visible while saving freezes editing',()=>{
 render(<RecordGridCellEditor field={field} rowNumber={1} cell={scalarDraft('正在核验的输入')} active disabled onActivate={vi.fn()} onChange={vi.fn()} onMove={vi.fn()} onPasteGrid={vi.fn()} onSave={vi.fn()} onUndo={vi.fn()}/>)
 expect(screen.getByText('正在核验的输入')).toBeTruthy()
 expect(screen.getByRole('gridcell').getAttribute('aria-readonly')).toBe('true')
})
it('opening a boolean editor does not silently write false',()=>{
 const onChange=vi.fn()
 render(<RecordGridCellEditor field={{...field,type:'boolean'}} rowNumber={1} cell={scalarDraft(undefined)} active onActivate={vi.fn()} onChange={onChange} onMove={vi.fn()} onPasteGrid={vi.fn()} onSave={vi.fn()} onUndo={vi.fn()}/>)
 fireEvent.keyDown(screen.getByRole('gridcell'),{key:'t'})
 expect(onChange).not.toHaveBeenCalled()
 expect(document.activeElement).toBe(screen.getByRole('combobox'))
 fireEvent.keyDown(screen.getByRole('combobox'),{key:'Escape'})
 expect(screen.queryByRole('combobox')).toBeNull()
})
