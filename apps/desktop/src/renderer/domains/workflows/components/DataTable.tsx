// Source: WebRPA@5ccb900e, components/workflow/DataTable.tsx; see SOURCE.md for license and adaptation boundaries.
/**
 * 高性能数据表格 - 用虚拟滚动渲染，无论多少行都能 60fps。
 * 仅渲染可视行 + overscan，编辑/删除/列管理保持原有行为。
 */
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Edit2, Trash2, X, ArrowUp, ArrowDown, Search } from 'lucide-react'
import { Button } from './controls/button'
import { Input } from './controls/input'
import { useVirtualizer } from '../hooks/useVirtualizer'
import type { DataRow } from '../editor-store'
import '../styles/table-system.css'

const ROW_HEIGHT = 32
const HEADER_HEIGHT = 32

interface DataTableProps {
  data: DataRow[]
  columns: string[]
  onEdit: (rowIndex: number, col: string, value: unknown) => void
  onDeleteRow: (rowIndex: number) => void
  onDeleteColumn: (col: string) => void
  /** 预览顺序：tail=最新（跟随底部新数据），head=最早（停在顶部） */
  displayMode?: 'tail' | 'head'
  /** 预览条数（变化时触发重新定位，便于用户看到改动立即生效） */
  displayLimit?: number
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

export const DataTable = memo(function DataTable({
  data,
  columns,
  onEdit,
  onDeleteRow,
  onDeleteColumn,
  displayMode = 'tail',
  displayLimit = 0,
}: DataTableProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const headerRef = useRef<HTMLDivElement>(null)
  const getScrollElement = useCallback(() => scrollRef.current, [])
  const [editingCell, setEditingCell] = useState<{ row: number; col: string } | null>(null)
  const [editValue, setEditValue] = useState('')
  // 列排序状态（点击列头：升→降→取消）
  const [sortCol, setSortCol] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  // 行筛选关键词（任意单元格包含即匹配）
  const [filterText, setFilterText] = useState('')

  // 显示顺序的原始索引映射（筛选 + 排序只影响展示，编辑/删除仍按原始索引回传，保证索引映射正确）
  const viewIndex = useMemo(() => {
    let idx = data.map((_, i) => i)
    const q = filterText.trim().toLowerCase()
    if (q) {
      idx = idx.filter((i) => {
        const row = data[i]
        return columns.some((c) => formatCellValue(row?.[c]).toLowerCase().includes(q))
      })
    }
    if (!sortCol) return idx
    const num = (v: unknown) => {
      const n = typeof v === 'number' ? v : parseFloat(String(v ?? '').replace(/[, ]/g, ''))
      return Number.isFinite(n) ? n : null
    }
    idx.sort((a, b) => {
      const va = data[a]?.[sortCol]
      const vb = data[b]?.[sortCol]
      const na = num(va), nb = num(vb)
      let cmp: number
      if (na !== null && nb !== null) cmp = na - nb
      else cmp = String(va ?? '').localeCompare(String(vb ?? ''), 'zh')
      return sortDir === 'asc' ? cmp : -cmp
    })
    return idx
  }, [data, columns, filterText, sortCol, sortDir])

  const toggleSort = (col: string) => {
    if (sortCol !== col) { setSortCol(col); setSortDir('asc') }
    else if (sortDir === 'asc') setSortDir('desc')
    else { setSortCol(null); setSortDir('asc') }
  }

  const { virtualItems, totalSize, scrollToBottom, scrollToTop } = useVirtualizer({
    count: viewIndex.length,
    getScrollElement,
    estimateSize: ROW_HEIGHT,
    overscan: 8,
  })

  // 用户切换“最新/最早”或预览条数时，立即重新定位，让改动可见：
  // tail → 滚到底部（看最新行），head → 滚到顶部（看最早行）。
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      if (displayMode === 'head') scrollToTop()
      else scrollToBottom()
    })
    return () => cancelAnimationFrame(id)

  }, [displayMode, displayLimit])

  // “最新”模式下执行过程中持续跟随新增数据滚到底部
  const prevLenRef = useRef(data.length)
  useEffect(() => {
    if (data.length !== prevLenRef.current) {
      prevLenRef.current = data.length
      if (displayMode === 'tail') {
        const id = requestAnimationFrame(() => scrollToBottom())
        return () => cancelAnimationFrame(id)
      }
    }

  }, [data.length, displayMode])

  const startEdit = (row: number, col: string, value: unknown) => {
    setEditingCell({ row, col })
    setEditValue(formatCellValue(value))
  }

  const saveEdit = () => {
    if (!editingCell) return
    onEdit(editingCell.row, editingCell.col, editValue)
    setEditingCell(null)
    setEditValue('')
  }

  const cancelEdit = () => {
    setEditingCell(null)
    setEditValue('')
  }

  // 计算列宽（保持每列 min-w-[120px]）
  const columnWidth = 140
  const idColumnWidth = 60
  const actionColumnWidth = 60
  const tableWidth = idColumnWidth + columns.length * columnWidth + actionColumnWidth

  return (
    <div className="af-studio-data-grid flex h-full min-h-0 min-w-0 flex-col">
      {/* 筛选工具栏 */}
      <div className="af-table-toolbar flex min-h-8 items-center gap-2 border-b border-[hsl(var(--border))] bg-[hsl(var(--card))] px-2 flex-shrink-0">
        <div className="relative flex-1 max-w-[260px]">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[hsl(var(--muted-foreground))]" />
          <input
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            placeholder="筛选数据（任意列包含）…"
            className="h-8 w-full rounded-control border border-[hsl(var(--border))] bg-[hsl(var(--slate-50))] pl-7 pr-7 text-sm focus:border-[hsl(var(--brand-500))] focus:bg-[hsl(var(--card))] focus:outline-none"
          />
          {filterText && (
            <button
              onClick={() => setFilterText('')}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--danger-600))]"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
        <span className="text-sm leading-5 text-[hsl(var(--muted-foreground))] tabular-nums">
          {filterText ? `匹配 ${viewIndex.length} / ${data.length} 行` : `${data.length} 行`}
          {sortCol && <span className="ml-2">· 按「{sortCol}」{sortDir === 'asc' ? '升序' : '降序'}</span>}
        </span>
      </div>
      {/* 表头与正文共用横向滚动容器，避免宽表滚动后错列。 */}
      <div className="af-table-scroll af-studio-grid-scroll flex min-h-0 flex-1 flex-col" style={{ overflow: 'hidden' }}>
      <div className="w-full flex-shrink-0 overflow-hidden">
      <div
        ref={headerRef}
        className="af-studio-grid-header flex text-sm font-medium"
        style={{ height: HEADER_HEIGHT, width: tableWidth }}
      >
        <div
          className="flex items-center justify-center border-r border-[hsl(var(--border))] flex-shrink-0"
          style={{ width: idColumnWidth }}
        >
          #
        </div>
        {columns.map((col) => (
          <div
            key={col}
            className="flex items-center justify-between px-2 border-r border-[hsl(var(--border))] flex-shrink-0 group/col"
            style={{ width: columnWidth }}
          >
            <button
              className="flex items-center gap-1 min-w-0 flex-1 text-left hover:text-[hsl(var(--brand-600))] transition-colors"
              onClick={() => toggleSort(col)}
              title="点击排序（升序 / 降序 / 取消）"
            >
              <span className="truncate">{col}</span>
              {sortCol === col && (sortDir === 'asc'
                ? <ArrowUp className="w-3 h-3 flex-shrink-0 text-[hsl(var(--brand-600))]" />
                : <ArrowDown className="w-3 h-3 flex-shrink-0 text-[hsl(var(--brand-600))]" />)}
            </button>
            <Button
              variant="ghost"
              size="icon"
              className="w-5 h-5 opacity-50 hover:opacity-100 flex-shrink-0"
              onClick={() => onDeleteColumn(col)}
              aria-label={`删除列 ${col}`}
            >
              <X className="w-3 h-3" />
            </Button>
          </div>
        ))}
        <div
          className="flex items-center justify-center flex-shrink-0"
          style={{ width: actionColumnWidth }}
        >
          操作
        </div>
      </div>
      </div>

      {/* 行区 - 虚拟滚动 */}
      <div
        ref={scrollRef}
        role="region"
        aria-label="数据预览"
        tabIndex={0}
        className="af-studio-grid-body min-h-0 w-full flex-1 overflow-auto"
        onScroll={(event) => {
          if (headerRef.current) headerRef.current.style.transform = `translateX(-${event.currentTarget.scrollLeft}px)`
        }}
      >
        <div style={{ height: totalSize, minWidth: tableWidth, position: 'relative' }}>
          {virtualItems.map((v) => {
            const origIndex = viewIndex[v.index]
            const row = data[origIndex]
            if (!row) return null
            const rowIndex = origIndex
            return (
              <div
                key={rowIndex}
                style={{
                  position: 'absolute',
                  top: v.start,
                  left: 0,
                  height: ROW_HEIGHT,
                  width: tableWidth,
                }}
                className="af-studio-grid-row flex text-sm"
              >
                <div
                  className="flex items-center justify-center text-[hsl(var(--muted-foreground))] border-r border-[hsl(var(--border))] flex-shrink-0"
                  style={{ width: idColumnWidth }}
                >
                  {rowIndex + 1}
                </div>
                {columns.map((col) => {
                  const value = row[col]
                  const isEditing = editingCell?.row === rowIndex && editingCell?.col === col
                  return (
                    <div
                      key={col}
                      className="flex items-center px-2 border-r border-[hsl(var(--border))] cursor-pointer hover:bg-[hsl(var(--muted))] group flex-shrink-0"
                      style={{ width: columnWidth }}
                      onClick={() => !isEditing && startEdit(rowIndex, col, value)}
                    >
                      {isEditing ? (
                        <Input
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="h-6 text-xs w-full"
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') saveEdit()
                            if (e.key === 'Escape') cancelEdit()
                          }}
                          onBlur={saveEdit}
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <>
                          <span className="truncate flex-1" title={formatCellValue(value)}>
                            {formatCellValue(value)}
                          </span>
                          <Edit2 className="w-3 h-3 opacity-0 group-hover:opacity-50 flex-shrink-0" />
                        </>
                      )}
                    </div>
                  )
                })}
                <div
                  className="flex items-center justify-center flex-shrink-0"
                  style={{ width: actionColumnWidth }}
                >
                  <Button
                    variant="ghost"
                    size="icon"
                    className="w-5 h-5"
                    onClick={() => onDeleteRow(rowIndex)}
                    aria-label={`删除第 ${rowIndex + 1} 行`}
                  >
                    <Trash2 className="w-3 h-3 text-[hsl(var(--danger-500))]" />
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      </div>
      </div>
    </div>
  )
})
