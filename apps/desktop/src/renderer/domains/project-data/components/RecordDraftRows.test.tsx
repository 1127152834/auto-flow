import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { RecordDraftRows } from './RecordDraftRows'
import { newDraftRow } from '../record-grid-draft'
import { scalarDraft } from '../scalar-draft'
afterEach(cleanup)
const field={ref:{projectId:'p',tableId:'t',datasetGeneration:'g',fieldId:'f'},key:'title',name:'标题',type:'string' as const,required:true,validation:{},writable:true,formula:false,fieldRevision:1}
const handlers=()=>({onAdd:vi.fn(),onRemove:vi.fn(),onCellChange:vi.fn(),onPaste:vi.fn(),onSave:vi.fn(),onUndo:vi.fn()})
it('aligns draft cells with identity business status updated time and action columns',()=>{
 const row=newDraftRow([field]), props=handlers()
 render(<table><tbody><RecordDraftRows rows={[row]} fields={[field]} errors={[]} selectionColumn {...props}/></tbody></table>)
 const rows=screen.getAllByRole('row')
 expect(rows[0].children).toHaveLength(6)
 expect(within(rows[0]).getByText('未保存')).toBeTruthy()
 expect(rows[1].children[0].getAttribute('colspan')).toBe('6')
 fireEvent.click(screen.getByRole('button',{name:'移除第 1 行草稿'}));expect(props.onRemove).toHaveBeenCalledWith(row.clientRowId)
 expect(screen.queryByRole('dialog')).toBeNull()
})
it('shows typed business identity input without allocating a system identifier',()=>{
 const row=newDraftRow([field]);row.cells.f=scalarDraft('001')
 render(<table><tbody><RecordDraftRows rows={[row]} fields={[field]} identityFieldId="f" errors={[]} {...handlers()}/></tbody></table>)
 expect(screen.queryByText('保存后生成')).toBeNull()
 expect(screen.getAllByText('001')).toHaveLength(2)
})
it('does not trap in an unbounded navigation loop when every field is readonly',()=>{
 const readonly={...field,writable:false}, props=handlers()
 render(<table><tbody><RecordDraftRows rows={[newDraftRow([readonly])]} fields={[readonly]} errors={[]} {...props}/></tbody></table>)
 fireEvent.keyDown(screen.getByRole('gridcell'),{key:'Tab'})
 expect(props.onAdd).not.toHaveBeenCalled()
})
it('keeps the current column when Enter appends the next row',()=>{
 const second={...field,key:'url',name:'链接',ref:{...field.ref,fieldId:'url'}}, props=handlers()
 render(<table><tbody><RecordDraftRows rows={[newDraftRow([field,second])]} fields={[field,second]} errors={[]} {...props}/></tbody></table>)
 fireEvent.keyDown(screen.getByRole('gridcell',{name:'第 1 行 · 链接'}),{key:'Enter'})
 expect(props.onAdd).toHaveBeenCalledWith('url')
})
it('moves focus to the save controls at the 100-row limit',()=>{
 render(<><table><tbody><RecordDraftRows rows={Array.from({length:100},()=>newDraftRow([field]))} fields={[field]} errors={[]} {...handlers()}/></tbody></table><footer aria-label="新增记录保存"><button>保存</button></footer></>)
 fireEvent.keyDown(screen.getByRole('gridcell',{name:'第 100 行 · 标题'}),{key:'Tab'})
 expect(document.activeElement).toBe(screen.getByRole('button',{name:'保存'}))
})
