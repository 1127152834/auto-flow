// Source: WebRPA@5ccb900e, components/workflow/config-panels/ExcelPreviewDialog.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { Button } from '../controls/button'
import { dataAssetApi } from '../../api'
import { cn } from '../../lib/utils'

interface ExcelPreviewDialogProps {
  open: boolean
  onClose: () => void
  fileId: string
  fileName: string
  sheetName?: string
  mode?: 'cell' | 'row' | 'column' | 'range'
  onSelect?: (selection: SelectionResult) => void
  previewOnly?: boolean  // 纯预览模式，不需要选择功能
}

export interface SelectionResult {
  mode: 'cell' | 'row' | 'column' | 'range'
  cellAddress?: string
  rowIndex?: number
  columnIndex?: string
  startCell?: string
  endCell?: string
}

// 列索引转字母
function colIndexToLetter(index: number): string {
  let result = ''
  while (index >= 0) {
    result = String.fromCharCode((index % 26) + 65) + result
    index = Math.floor(index / 26) - 1
  }
  return result
}

export function ExcelPreviewDialog({
  open,
  onClose,
  fileId,
  fileName,
  sheetName,
  mode = 'cell',
  onSelect,
  previewOnly = false,
}: ExcelPreviewDialogProps) {
  const [data, setData] = useState<string[][]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [totalRows, setTotalRows] = useState(0)
  const [totalCols, setTotalCols] = useState(0)
  
  // 选择状态
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number } | null>(null)
  const [selectedRow, setSelectedRow] = useState<number | null>(null)
  const [selectedCol, setSelectedCol] = useState<number | null>(null)
  const [rangeStart, setRangeStart] = useState<{ row: number; col: number } | null>(null)
  const [rangeEnd, setRangeEnd] = useState<{ row: number; col: number } | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  // 加载预览数据
  useEffect(() => {
    if (open && fileId) {
      setLoading(true)
      setError(null)
      dataAssetApi.preview(fileId, sheetName).then(res => {
        if (res.data) {
          setData(res.data.data)
          setTotalRows(res.data.totalRows)
          setTotalCols(res.data.totalCols)
        }
      }).catch(err => {
        setError(err.message || '加载失败')
      }).finally(() => {
        setLoading(false)
      })
    }
  }, [open, fileId, sheetName])

  // 重置选择
  useEffect(() => {
    if (open) {
      setSelectedCell(null)
      setSelectedRow(null)
      setSelectedCol(null)
      setRangeStart(null)
      setRangeEnd(null)
      setIsDragging(false)
    }
  }, [open, mode])

  // 处理鼠标按下
  const handleCellMouseDown = useCallback((rowIdx: number, colIdx: number) => {
    if (previewOnly) return
    
    if (mode === 'cell') {
      setSelectedCell({ row: rowIdx, col: colIdx })
    } else if (mode === 'row') {
      setSelectedRow(rowIdx)
    } else if (mode === 'column') {
      setSelectedCol(colIdx)
    } else if (mode === 'range') {
      setRangeStart({ row: rowIdx, col: colIdx })
      setRangeEnd({ row: rowIdx, col: colIdx })
      setIsDragging(true)
    }
  }, [mode, previewOnly])

  // 处理鼠标移动
  const handleCellMouseEnter = useCallback((rowIdx: number, colIdx: number) => {
    if (previewOnly) return
    
    if (mode === 'range' && isDragging && rangeStart) {
      setRangeEnd({ row: rowIdx, col: colIdx })
    }
  }, [mode, isDragging, rangeStart, previewOnly])

  // 处理鼠标释放
  const handleMouseUp = useCallback(() => {
    if (mode === 'range') {
      setIsDragging(false)
    }
  }, [mode])

  // 处理行头点击
  const handleRowHeaderClick = useCallback((rowIdx: number) => {
    if (previewOnly) return
    if (mode === 'row') {
      setSelectedRow(rowIdx)
    }
  }, [mode, previewOnly])

  // 处理列头点击
  const handleColHeaderClick = useCallback((colIdx: number) => {
    if (previewOnly) return
    if (mode === 'column') {
      setSelectedCol(colIdx)
    }
  }, [mode, previewOnly])

  // 检查单元格是否被选中
  const isCellSelected = useCallback((rowIdx: number, colIdx: number) => {
    if (previewOnly) return false
    
    if (mode === 'cell' && selectedCell) {
      return selectedCell.row === rowIdx && selectedCell.col === colIdx
    }
    if (mode === 'row' && selectedRow !== null) {
      return selectedRow === rowIdx
    }
    if (mode === 'column' && selectedCol !== null) {
      return selectedCol === colIdx
    }
    if (mode === 'range' && rangeStart && rangeEnd) {
      const minRow = Math.min(rangeStart.row, rangeEnd.row)
      const maxRow = Math.max(rangeStart.row, rangeEnd.row)
      const minCol = Math.min(rangeStart.col, rangeEnd.col)
      const maxCol = Math.max(rangeStart.col, rangeEnd.col)
      return rowIdx >= minRow && rowIdx <= maxRow && colIdx >= minCol && colIdx <= maxCol
    }
    return false
  }, [mode, selectedCell, selectedRow, selectedCol, rangeStart, rangeEnd, previewOnly])

  // 确认选择
  const handleConfirm = useCallback(() => {
    if (!onSelect) return
    
    const result: SelectionResult = { mode }
    
    if (mode === 'cell' && selectedCell) {
      result.cellAddress = `${colIndexToLetter(selectedCell.col)}${selectedCell.row + 1}`
    } else if (mode === 'row' && selectedRow !== null) {
      result.rowIndex = selectedRow + 1
    } else if (mode === 'column' && selectedCol !== null) {
      result.columnIndex = colIndexToLetter(selectedCol)
    } else if (mode === 'range' && rangeStart && rangeEnd) {
      const minRow = Math.min(rangeStart.row, rangeEnd.row)
      const maxRow = Math.max(rangeStart.row, rangeEnd.row)
      const minCol = Math.min(rangeStart.col, rangeEnd.col)
      const maxCol = Math.max(rangeStart.col, rangeEnd.col)
      result.startCell = `${colIndexToLetter(minCol)}${minRow + 1}`
      result.endCell = `${colIndexToLetter(maxCol)}${maxRow + 1}`
    } else {
      return // 没有选择
    }
    
    onSelect(result)
    onClose()
  }, [mode, selectedCell, selectedRow, selectedCol, rangeStart, rangeEnd, onSelect, onClose])

  // 获取选择提示文本
  const getSelectionHint = () => {
    if (previewOnly) return '数据预览'
    switch (mode) {
      case 'cell': return '点击选择单元格'
      case 'row': return '点击行号或任意单元格选择整行'
      case 'column': return '点击列头或任意单元格选择整列'
      case 'range': return '按住鼠标拖动选择范围'
    }
  }

  // 获取当前选择的描述
  const getSelectionDesc = () => {
    if (mode === 'cell' && selectedCell) {
      return `${colIndexToLetter(selectedCell.col)}${selectedCell.row + 1}`
    }
    if (mode === 'row' && selectedRow !== null) {
      return `第 ${selectedRow + 1} 行`
    }
    if (mode === 'column' && selectedCol !== null) {
      return `${colIndexToLetter(selectedCol)} 列`
    }
    if (mode === 'range' && rangeStart && rangeEnd) {
      const minRow = Math.min(rangeStart.row, rangeEnd.row)
      const maxRow = Math.max(rangeStart.row, rangeEnd.row)
      const minCol = Math.min(rangeStart.col, rangeEnd.col)
      const maxCol = Math.max(rangeStart.col, rangeEnd.col)
      return `${colIndexToLetter(minCol)}${minRow + 1} : ${colIndexToLetter(maxCol)}${maxRow + 1}`
    }
    return '未选择'
  }

  if (!open) return null

  return createPortal(
    <div 
      className="fixed inset-0 flex items-center justify-center bg-black/40 animate-fade-in"
      style={{ zIndex: 2147483646 }}
      onMouseUp={handleMouseUp}
    >
      <div className="bg-white rounded-xl shadow-2xl w-[90vw] max-w-5xl h-[80vh] flex flex-col overflow-hidden animate-scale-in">
        {/* 头部 */}
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <div>
            <h3 className="font-medium">Excel 预览 - {fileName}</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {getSelectionHint()} | 共 {totalRows} 行 × {totalCols} 列
            </p>
          </div>
          <Button variant="tonal-danger" size="icon" onClick={onClose} title="关闭">

            <X className="w-4 h-4" />

          </Button>
        </div>

        {/* 表格区域 */}
        <div className="flex-1 overflow-auto p-2">
          {loading && (
            <div className="flex items-center justify-center h-full">
              <div className="text-gray-500">加载中...</div>
            </div>
          )}
          {error && (
            <div className="flex items-center justify-center h-full">
              <div className="text-red-500">{error}</div>
            </div>
          )}
          {!loading && !error && data.length > 0 && (
            <table className="border-collapse text-sm select-none">
              <thead>
                <tr>
                  <th className="sticky top-0 left-0 z-20 bg-gray-100 border border-gray-300 px-2 py-1 min-w-[40px]" />
                  {data[0]?.map((_, colIdx) => (
                    <th
                      key={colIdx}
                      onMouseDown={() => handleColHeaderClick(colIdx)}
                      className={cn(
                        'sticky top-0 z-10 bg-gray-100 border border-gray-300 px-2 py-1 min-w-[80px] font-medium',
                        !previewOnly && mode === 'column' && 'cursor-pointer hover:bg-blue-100',
                        selectedCol === colIdx && 'bg-blue-200'
                      )}
                    >
                      {colIndexToLetter(colIdx)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.map((row, rowIdx) => (
                  <tr key={rowIdx}>
                    <td
                      onMouseDown={() => handleRowHeaderClick(rowIdx)}
                      className={cn(
                        'sticky left-0 z-10 bg-gray-100 border border-gray-300 px-2 py-1 text-center font-medium',
                        !previewOnly && mode === 'row' && 'cursor-pointer hover:bg-blue-100',
                        selectedRow === rowIdx && 'bg-blue-200'
                      )}
                    >
                      {rowIdx + 1}
                    </td>
                    {row.map((cell, colIdx) => (
                      <td
                        key={colIdx}
                        onMouseDown={() => handleCellMouseDown(rowIdx, colIdx)}
                        onMouseEnter={() => handleCellMouseEnter(rowIdx, colIdx)}
                        className={cn(
                          'border border-gray-300 px-2 py-1 max-w-[200px] truncate',
                          !previewOnly && 'cursor-pointer hover:bg-gray-50',
                          isCellSelected(rowIdx, colIdx) && 'bg-blue-100 hover:bg-blue-100'
                        )}
                        title={cell}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* 底部操作栏 - 仅在选择模式下显示 */}
        {!previewOnly && (
          <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50 rounded-b-lg">
            <div className="text-sm">
              <span className="text-gray-500">当前选择：</span>
              <span className="font-medium text-blue-600 ml-1">{getSelectionDesc()}</span>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={onClose}>取消</Button>
              <Button onClick={handleConfirm}>确认选择</Button>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}
