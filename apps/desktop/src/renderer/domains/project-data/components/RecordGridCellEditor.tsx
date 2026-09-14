import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../../../shared/components/ui/dropdown-menu'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Textarea } from '../../../shared/components/ui/textarea'
import { scalarDraft } from '../scalar-draft'
import type { GridCell, GridField } from '../record-grid-draft'

export type GridMove = 'next' | 'previous' | 'down' | 'up'
type Props = {
  field: GridField; rowNumber: number; cell: GridCell; active: boolean; disabled?: boolean; error?: string
  onActivate(): void; onChange(cell: GridCell): void; onMove(move: GridMove): void
  onPasteGrid(text: string): void; onSave(): void; onUndo(): void
}
export function RecordGridCellEditor({ field, rowNumber, cell, active, disabled, error, onActivate, onChange, onMove, onPasteGrid, onSave, onUndo }: Props) {
  const [editing, setEditing] = useState(false)
  const booleanSelect = useRef<HTMLButtonElement>(null)
  useEffect(() => { if (editing && field.type === 'boolean') booleanSelect.current?.focus() }, [editing, field.type])
  const previous = useRef(cell), root = useRef<HTMLDivElement>(null), errorId = useId()
  useEffect(() => { if (!active) setEditing(false) }, [active])
  const locked = disabled || !field.writable || field.formula
  const label = `第 ${rowNumber} 行 · ${field.name}`
  const start = () => { if (!locked) { previous.current = cell; setEditing(true); onActivate() } }
  const finish = () => { setEditing(false); root.current?.focus() }
  const change = (patch: Partial<GridCell>) => onChange({ ...cell, inputError: undefined, ...patch })
  const keyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (locked || event.nativeEvent.isComposing || event.defaultPrevented) return
    const target = event.target as HTMLElement
    const ownControl = event.target === event.currentTarget || ['INPUT', 'TEXTAREA'].includes(target.tagName)
      || target.getAttribute('role') === 'combobox' && target.getAttribute('aria-expanded') !== 'true' && ['Tab', 'Escape'].includes(event.key)
    if (!ownControl) return // Radix controls own their keyboard and nested Escape.
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); onSave(); return }
    if (event.key === 'Escape' && editing) { event.preventDefault(); event.stopPropagation(); onChange(previous.current); finish(); return }
    if (event.key === 'Tab' || (event.key === 'Enter' && !event.shiftKey)) {
      event.preventDefault(); setEditing(false); onMove(event.key === 'Enter' ? 'down' : event.shiftKey ? 'previous' : 'next'); return
    }
    if (editing) return
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); onUndo(); return }
    if (event.key === 'Delete' || event.key === 'Backspace') { event.preventDefault(); onChange(scalarDraft(undefined)); return }
    const arrows: Record<string, GridMove> = { ArrowRight: 'next', ArrowLeft: 'previous', ArrowDown: 'down', ArrowUp: 'up' }
    if (arrows[event.key]) { event.preventDefault(); onMove(arrows[event.key]); return }
    if (event.key === 'F2') { event.preventDefault(); start() }
    else if (event.key.length === 1 && !event.metaKey && !event.ctrlKey && !event.altKey) {
      event.preventDefault(); start(); if (field.type !== 'boolean') change({ presence: 'value', text: event.key })
    }
  }
  const value = cell.presence === 'missing' ? '未填写' : cell.presence === 'null' ? '空值' : cell.inputError ? cell.text : field.type === 'boolean' ? cell.boolean ? '是' : '否' : cell.text === '' ? '空文本' : cell.text
  return <div ref={root} role="gridcell" aria-label={label} aria-readonly={locked || undefined} aria-invalid={Boolean(error) || undefined} aria-describedby={error ? errorId : undefined}
    tabIndex={active && !locked ? 0 : -1} data-grid-cell={`${rowNumber - 1}:${field.ref.fieldId}`}
    className={`relative min-h-11 min-w-0 rounded-sm border px-2 py-1 text-sm ${error ? 'border-danger' : active ? 'border-clay' : 'border-transparent'} focus:outline-2 focus:outline-focus`}
    onFocus={onActivate} onClick={onActivate} onDoubleClick={start} onKeyDown={keyDown}
    onPaste={event => { if (!editing && !locked) { event.preventDefault(); onPasteGrid(event.clipboardData.getData('text/plain')) } }}>
    {editing && !locked ? <div className="grid min-w-0 gap-1">
      {field.type === 'boolean' ? <Select ref={booleanSelect} aria-label={label} value={cell.presence === 'value' && !cell.inputError ? String(cell.boolean) : null} options={[{ value: 'true', label: '是' }, { value: 'false', label: '否' }]} clearable={false} onValueChange={v => change({ presence: 'value', boolean: v === 'true' })} />
        : field.type === 'string' ? <Textarea autoFocus aria-label={label} aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined} rows={cell.text.includes('\n') ? 3 : 1} className="min-h-9 resize-y px-1 py-1" value={cell.presence === 'value' ? cell.text : ''} onChange={event => change({ presence: 'value', text: event.target.value })} />
        : <Input autoFocus aria-label={label} aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined} inputMode={field.type === 'number' ? 'decimal' : undefined} placeholder={field.type === 'date' ? cell.precision === 'date' ? 'YYYY-MM-DD' : 'YYYY-MM-DDTHH:mm:ss' : undefined} value={cell.presence === 'value' ? cell.text : ''} onChange={event => change({ presence: 'value', text: event.target.value })} />}
      {field.type === 'date' ? <><Select aria-label={`${label}精度`} value={cell.precision} clearable={false} options={[{ value: 'date', label: '日期' }, { value: 'datetime', label: '日期时间' }]} onValueChange={v => change({ precision: v === 'datetime' ? 'datetime' : 'date', offset: v === 'date' ? '' : cell.offset })} />{cell.precision === 'datetime' ? <Input aria-label={`${label}时区偏移`} placeholder="留空、Z 或 +08:00" value={cell.offset} onChange={e => change({ offset: e.target.value })} /> : null}</> : null}
    </div> : <span className={`block min-w-0 truncate py-1.5 ${cell.presence === 'missing' ? 'text-muted' : 'text-ink'}`} title={value}>{cell.presence === 'missing' && (!field.writable || field.formula) ? '不可填写' : value}</span>}
    {active && !locked ? <DropdownMenu><DropdownMenuTrigger asChild><Button size="sm" variant="ghost" className="absolute right-0 top-0 h-6 px-1 text-xs" aria-label={`${label}值选项`}>⋯</Button></DropdownMenuTrigger><DropdownMenuContent>
      <DropdownMenuItem onSelect={() => { onChange(scalarDraft(undefined)); finish() }}>留空（未填写）</DropdownMenuItem>
      <DropdownMenuItem onSelect={() => { onChange(scalarDraft(null)); finish() }}>设为空值</DropdownMenuItem>
      {field.type === 'string' ? <DropdownMenuItem onSelect={() => { onChange(scalarDraft('')); finish() }}>设为空文本</DropdownMenuItem> : null}
      <DropdownMenuItem onSelect={start}>编辑单元格</DropdownMenuItem>
    </DropdownMenuContent></DropdownMenu> : null}
    {error ? <p id={errorId} className="mt-1 text-xs text-danger">{error}</p> : null}
  </div>
}
