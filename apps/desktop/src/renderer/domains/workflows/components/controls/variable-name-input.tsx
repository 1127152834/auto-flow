// Source: WebRPA@5ccb900e, components/ui/variable-name-input.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState, useRef, useEffect, useMemo } from 'react'
import { Input } from './input'
import { cn } from '../../lib/utils'
import { useWorkflowStore } from '../../editor-store'
import { getModuleDefaultVar, VARIABLE_NAME_FIELDS } from '../../lib/moduleDefaultVars'
import type { Variable } from '../../types/index'



interface VariableNameInputProps {
  id?: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
  /** 是否启用重命名检测（当变量名变更时检查是否有引用），默认启用 */
  enableRenameDetection?: boolean
  /** 是否是存储变量名输入框（不显示"变量不存在"提示），默认 false */
  isStorageVariable?: boolean
}

// 重命名确认弹窗
function RenameConfirmDialog({
  oldName,
  newName,
  usageCount,
  onConfirm,
  onCancel,
}: {
  oldName: string
  newName: string
  usageCount: number
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/50 backdrop-blur-sm" style={{ zIndex: 2147483640 }}>
      <div className="bg-white rounded-2xl shadow-2xl w-[420px] mx-4 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* 顶部渐变装饰 */}
        <div className="bg-[hsl(var(--card))] h-1.5" />
        
        <div className="p-6">
          {/* 图标和标题 */}
          <div className="flex items-center gap-3 mb-5">
            <div className="bg-[hsl(var(--card))] w-10 h-10 rounded-xl flex items-center justify-center shadow-lg">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">变量重命名</h3>
              <p className="text-xs text-gray-500">检测到变量引用需要更新</p>
            </div>
          </div>
          
          {/* 变量变更展示 */}
          <div className="bg-[hsl(var(--card))] rounded-xl p-4 mb-5">
            <div className="flex items-center justify-center gap-3">
              <div className="flex items-center gap-2 px-3 py-2 bg-white rounded-lg shadow-sm border border-gray-200">
                <span className="text-xs text-gray-500">原名</span>
                <code className="text-sm font-mono font-semibold text-red-600">{'{' + oldName + '}'}</code>
              </div>
              <div className="bg-[hsl(var(--card))] flex items-center justify-center w-8 h-8 rounded-full shadow-md">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </div>
              <div className="flex items-center gap-2 px-3 py-2 bg-white rounded-lg shadow-sm border border-gray-200">
                <span className="text-xs text-gray-500">新名</span>
                <code className="text-sm font-mono font-semibold text-emerald-600">{'{' + newName + '}'}</code>
              </div>
            </div>
          </div>
          
          {/* 引用数量提示 */}
          <div className="flex items-center gap-2 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl mb-6">
            <svg className="w-5 h-5 text-amber-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm text-amber-800">
              发现 <span className="font-bold text-amber-900">{usageCount}</span> 处引用了此变量
            </p>
          </div>
          
          {/* 按钮组 */}
          <div className="flex gap-3">
            <button
              onClick={onCancel}
              className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-xl transition-all duration-200 hover:shadow-md active:scale-[0.98]"
            >
              仅改此处
            </button>
            <button
              onClick={onConfirm}
              className="bg-[hsl(var(--success-600))] hover:bg-[hsl(var(--success-700))] flex-1 px-4 py-2.5 text-sm font-medium text-white rounded-xl transition-colors duration-150 shadow-lg hover:shadow-success-glow"
            >
              全部更新
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * 变量名输入组件
 * 用于输入变量名，自动过滤非法字符，只允许字母、数字、下划线和中文
 * 支持模糊搜索已有变量名并自动补全
 * 当变量名变更时，如果发现有其他地方引用了旧变量名，会提示用户是否批量更新
 */
export function VariableNameInput({
  id,
  value,
  onChange,
  placeholder,
  className,
  enableRenameDetection = true,
  isStorageVariable = false,
}: VariableNameInputProps) {
  const [showRenameDialog, setShowRenameDialog] = useState(false)
  const [pendingNewName, setPendingNewName] = useState('')
  const [usageCount, setUsageCount] = useState(0)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const renameEdit = useRef<{ before: ReturnType<typeof useWorkflowStore.getState>; after: ReturnType<typeof useWorkflowStore.getState> } | false | null>(null)
  const previousValueRef = useRef(value)
  const isInitializedRef = useRef(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const suggestionsRef = useRef<HTMLDivElement>(null)
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => { if (blurTimer.current) clearTimeout(blurTimer.current) }, [value])
  
  const globalVariables = useWorkflowStore((state) => state.variables)
  const nodes = useWorkflowStore((state) => state.nodes)
  const findVariableUsages = useWorkflowStore((state) => state.findVariableUsages)
  const replaceVariableReferences = useWorkflowStore((state) => state.replaceVariableReferences)

  // 收集所有变量（全局变量 + 模块定义的变量）
  const allVariables = useMemo(() => {
    const variableMap = new Map<string, Variable>()
    
    // 添加全局变量
    globalVariables.forEach(v => {
      variableMap.set(v.name, v)
    })
    
    // 从节点配置中提取变量名
    nodes.forEach(node => {
      const data = node.data as Record<string, unknown>
      const moduleType = data.moduleType as string
      
      VARIABLE_NAME_FIELDS.forEach(field => {
        let varName = data[field] as string | undefined
        
        // 如果字段没有值，尝试用集中表里的默认变量名
        if (!varName || !varName.trim()) {
          varName = getModuleDefaultVar(moduleType, field)
        }
        
        if (typeof varName === 'string' && varName.trim() && !variableMap.has(varName)) {
          let varType: Variable['type'] = 'string'
          const moduleType = data.moduleType as string
          
          if (moduleType === 'foreach' && field === 'indexVariable') {
            varType = 'number'
          } else if (moduleType === 'foreach_dict' && field === 'indexVariable') {
            varType = 'number'
          } else if (moduleType === 'loop' && field === 'indexVariable') {
            varType = 'number'
          } else if (moduleType === 'list_length') {
            varType = 'number'
          } else if (moduleType === 'random_number') {
            varType = 'number'
          } else if (['list_sum', 'list_average', 'list_max', 'list_min', 'math_round', 'math_floor', 'math_modulo', 'math_abs', 'math_sqrt', 'math_power'].includes(moduleType)) {
            varType = 'number'
          } else if (['list_operation', 'list_get', 'dict_keys', 'string_split', 'list_sort', 'list_unique', 'list_slice'].includes(moduleType)) {
            varType = 'array'
          } else if (['dict_operation', 'dict_get', 'json_parse', 'api_request'].includes(moduleType)) {
            varType = 'object'
          } else if (moduleType === 'network_capture') {
            varType = 'array'
          } else if (moduleType === 'webhook_trigger' || moduleType === 'email_trigger' || moduleType === 'api_trigger') {
            varType = 'object'
          } else if (moduleType === 'element_change_trigger' && field === 'saveChangeInfo') {
            varType = 'object'
          } else if (moduleType === 'math_base_convert') {
            varType = 'string'
          }
          
          variableMap.set(varName, {
            name: varName,
            value: undefined,
            type: varType,
            scope: 'local'
          })
        }
      })
    })
    
    return Array.from(variableMap.values())
  }, [globalVariables, nodes])

  // 模糊搜索过滤变量列表
  const filteredVariables = useMemo(() => {
    if (!value) return allVariables
    const lower = value.toLowerCase()
    return allVariables.filter(v => v.name.toLowerCase().includes(lower))
  }, [allVariables, value])

  // 记录初始值（仅在组件首次挂载且有值时）
  useEffect(() => {
    if (!isInitializedRef.current && value) {
      previousValueRef.current = value
      isInitializedRef.current = true
    }
  }, [value])

  // 当选中索引变化时，自动滚动到选中项
  useEffect(() => {
    if (!showSuggestions || selectedIndex < 0 || selectedIndex >= filteredVariables.length) {
      return
    }

    const container = suggestionsRef.current
    if (!container) {
      return
    }

    // 使用 querySelector 直接找到选中的元素
    const selectedElement = container.querySelector(`[data-index="${selectedIndex}"]`) as HTMLElement
    if (!selectedElement) {
      return
    }

    // 获取容器和元素的位置信息
    const containerRect = container.getBoundingClientRect()
    const elementRect = selectedElement.getBoundingClientRect()

    // 如果元素在可视区域下方
    if (elementRect.bottom > containerRect.bottom) {
      const scrollAmount = elementRect.bottom - containerRect.bottom
      container.scrollTop += scrollAmount
    }
    // 如果元素在可视区域上方
    else if (elementRect.top < containerRect.top) {
      const scrollAmount = containerRect.top - elementRect.top
      container.scrollTop -= scrollAmount
    }
  }, [selectedIndex, showSuggestions, filteredVariables])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    // 过滤非法字符，只保留字母、数字、下划线和中文
    const filtered = newValue.replace(/[^a-zA-Z0-9_\u4e00-\u9fa5]/g, '')
    if (filtered !== value) {
      const store = useWorkflowStore.getState()
      if (renameEdit.current && renameEdit.current.after !== store) renameEdit.current = false
      if (renameEdit.current === null) {
        store.pushHistory()
        const before = useWorkflowStore.getState()
        renameEdit.current = { before, after: before }
      }
      onChange(filtered)
      if (renameEdit.current) renameEdit.current.after = useWorkflowStore.getState()
    }
    
    // 始终显示建议列表（输入为空时显示全部，有输入时显示匹配的）
    setShowSuggestions(true)
    setSelectedIndex(0)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || filteredVariables.length === 0) return

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex(prev => (prev + 1) % filteredVariables.length)
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex(prev => (prev - 1 + filteredVariables.length) % filteredVariables.length)
        break
      case 'Enter':
      case 'Tab':
        e.preventDefault()
        selectVariable(filteredVariables[selectedIndex].name)
        break
      case 'Escape':
        setShowSuggestions(false)
        break
    }
  }

  const selectVariable = (varName: string) => {
    onChange(varName)
    setShowSuggestions(false)
    renameEdit.current = null
    previousValueRef.current = varName
    inputRef.current?.focus()
  }

  const handleBlur = () => {
    // 延迟关闭，允许点击选项；字段切换/卸载时取消旧任务。
    if (blurTimer.current) clearTimeout(blurTimer.current)
    blurTimer.current = setTimeout(() => {
      setShowSuggestions(false)
      
      const oldName = previousValueRef.current
      const newName = value
      
      // 如果名称没变或为空，不处理
      if (!enableRenameDetection || oldName === newName || !oldName || !newName) {
        renameEdit.current = null
        previousValueRef.current = value
        return
      }
      
      // 检查是否有地方引用了旧变量名
      const usages = findVariableUsages(oldName)
      
      if (usages.length > 0) {
        setUsageCount(usages.length)
        setPendingNewName(newName)
        setShowRenameDialog(true)
      } else {
        renameEdit.current = null
        previousValueRef.current = value
      }
    }, 150)
  }

  const handleFocus = () => {
    // 点击输入框时显示所有变量建议
    setShowSuggestions(true)
    setSelectedIndex(0)
  }

  const handleConfirmRename = () => {
    if (value !== pendingNewName) { setShowRenameDialog(false); return }
    const oldName = previousValueRef.current
    replaceVariableReferences(oldName, pendingNewName, renameEdit.current || undefined)
    renameEdit.current = null
    previousValueRef.current = pendingNewName
    setShowRenameDialog(false)
  }

  const handleCancelRename = () => {
    renameEdit.current = null
    previousValueRef.current = value
    setShowRenameDialog(false)
  }

  // 获取变量类型颜色
  const getTypeColor = (type: string) => {
    switch (type) {
      case 'string': return 'text-green-600'
      case 'number': return 'text-blue-600'
      case 'boolean': return 'text-purple-600'
      case 'array': return 'text-orange-600'
      case 'object': return 'text-cyan-600'
      default: return 'text-gray-600'
    }
  }

  // 格式化变量值显示
  const formatValue = (val: unknown): string => {
    if (val === null || val === undefined) return 'null'
    if (typeof val === 'object') {
      try {
        const str = JSON.stringify(val)
        return str.length > 30 ? str.slice(0, 30) + '...' : str
      } catch {
        return String(val)
      }
    }
    const str = String(val)
    return str.length > 30 ? str.slice(0, 30) + '...' : str
  }

  return (
    <>
      <div className="relative">
        <Input
          ref={inputRef}
          id={id}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          onFocus={handleFocus}
          placeholder={placeholder}
          className={cn('font-mono', className)}
        />
        
        {/* 变量建议下拉框 */}
        {showSuggestions && filteredVariables.length > 0 && (
          <div 
            ref={suggestionsRef}
            className="absolute z-50 mt-1 w-full max-h-48 overflow-auto rounded-md border border-gray-200 bg-white shadow-lg animate-scale-in"
          >
            <div className="p-1">
              {filteredVariables.map((variable, index) => (
                <div
                  key={variable.name}
                  data-index={index}
                  className={cn(
                    'flex items-center justify-between px-2 py-1.5 text-sm rounded cursor-pointer transition-colors',
                    index === selectedIndex ? 'bg-blue-100 text-blue-900' : 'hover:bg-gray-100'
                  )}
                  onClick={() => selectVariable(variable.name)}
                  onMouseEnter={() => setSelectedIndex(index)}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-blue-600">{variable.name}</span>
                    <span className={cn('text-xs', getTypeColor(variable.type))}>
                      ({variable.type})
                    </span>
                  </div>
                  <span className="text-xs text-gray-500 truncate max-w-[120px]">
                    {formatValue(variable.value)}
                  </span>
                </div>
              ))}
            </div>
            <div className="border-t px-2 py-1 text-[10px] text-gray-500 bg-gray-50">
              ↑↓ 选择 · Enter 确认 · Esc 关闭
            </div>
          </div>
        )}
        
        {/* 无匹配变量时的提示 */}
        {showSuggestions && filteredVariables.length === 0 && (
          <div className="absolute z-50 mt-1 w-full rounded-md border border-gray-200 bg-white shadow-lg p-3 text-sm animate-scale-in">
            {value && !isStorageVariable ? (
              <div className="text-gray-500">
                未找到匹配的变量 "<span className="text-blue-600 font-mono">{value}</span>"
              </div>
            ) : (
              <div className="text-gray-500">
                {isStorageVariable ? '输入新变量名或选择已有变量' : '暂无可用变量'}
              </div>
            )}
          </div>
        )}
      </div>
      
      {/* 重命名确认弹窗 */}
      {showRenameDialog && (
        <RenameConfirmDialog
          oldName={previousValueRef.current}
          newName={pendingNewName}
          usageCount={usageCount}
          onConfirm={handleConfirmRename}
          onCancel={handleCancelRename}
        />
      )}
    </>
  )
}
