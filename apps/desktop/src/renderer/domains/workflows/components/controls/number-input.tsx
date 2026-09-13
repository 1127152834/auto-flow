// Source: WebRPA@5ccb900e, components/ui/number-input.tsx; see SOURCE.md for license and adaptation boundaries.
import * as React from 'react'
import { cn } from '../../lib/utils'
import { useWorkflowStore } from '../../editor-store'
import { getModuleDefaultVar, VARIABLE_NAME_FIELDS } from '../../lib/moduleDefaultVars'
import type { Variable } from '../../types/index'

export interface NumberInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'type' | 'value'> {
  value: number | string
  onChange: (value: number | string) => void
  defaultValue?: number
  min?: number
  max?: number
  step?: number
}

/**
 * 数字输入框组件 - 支持变量引用
 * - 输入时允许清空，失焦时保持为空
 * - 支持输入 {变量名} 引用变量
 * - 支持 min/max 限制
 */
const NumberInput = React.forwardRef<HTMLInputElement, NumberInputProps>(
  ({ className, value, onChange, defaultValue = 0, min, max, step: _step, ...props }, ref) => {
    const [displayValue, setDisplayValue] = React.useState<string>(String(value ?? defaultValue))
    const lastEmitted = React.useRef<{value: number | string} | null>(null)
    const errorId = React.useId()
    const [showSuggestions, setShowSuggestions] = React.useState(false)
    const [selectedIndex, setSelectedIndex] = React.useState(0)
    const [searchText, setSearchText] = React.useState('')
    const [cursorPosition, setCursorPosition] = React.useState(0)
    const inputRef = React.useRef<HTMLInputElement>(null)
    const suggestionsRef = React.useRef<HTMLDivElement>(null)
    
    const globalVariables = useWorkflowStore((state) => state.variables)
    const nodes = useWorkflowStore((state) => state.nodes)

    // 收集所有变量（全局变量 + 模块定义的变量 + 内置隐含变量）
    const allVariables = React.useMemo(() => {
      const variableMap = new Map<string, Variable>()
      
      // 首先添加内置隐含变量
      variableMap.set('ERROR', {
        name: 'ERROR',
        value: undefined,
        type: 'object',
        scope: 'global',
        description: '当模块报错或超时时，自动存入该模块的详细错误信息',
        builtin: true,
      })
      
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
          // 如果字段没有值，尝试用集中表里的默认变量名（识别模块创建时即内置的变量）
          if (!varName || !varName.trim()) {
            varName = getModuleDefaultVar(moduleType, field)
          }
          if (typeof varName === 'string' && varName.trim() && !variableMap.has(varName)) {
            // 根据模块类型推断变量类型
            let varType: Variable['type'] = 'string'
            
            // 推断变量类型
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

    // 合并 ref
    React.useImperativeHandle(ref, () => inputRef.current!)

    // 当外部 value 变化时同步
    React.useEffect(() => {
      if (lastEmitted.current && Object.is(value, lastEmitted.current.value)) {
        lastEmitted.current = null
        return
      }
      lastEmitted.current = null
      setDisplayValue(String(value ?? defaultValue))
    }, [value, defaultValue])

    // 检查是否包含变量引用
    const hasVariableRef = (val: string) => val.includes('{')
    const parseNumber = (text: string): number | null => {
      const trimmed = text.trim()
      if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(trimmed)) return null
      const parsed = Number(trimmed)
      return Number.isFinite(parsed) ? parsed : null
    }
    const parsedNumber = parseNumber(displayValue)
    const validationError = hasVariableRef(displayValue) || displayValue === '' ? ''
      : parsedNumber === null ? '请输入有效的有限数字或变量引用'
      : min !== undefined && parsedNumber < min ? `数值不能小于 ${min}`
      : max !== undefined && parsedNumber > max ? `数值不能大于 ${max}` : ''
    React.useEffect(() => { inputRef.current?.setCustomValidity(validationError) }, [validationError])
    const emitValue = (next: number | string) => {
      lastEmitted.current = {value: next}
      if (!Object.is(next, value)) onChange(next)
    }

    // 过滤变量列表
    const filteredVariables = React.useMemo(() => {
      if (!searchText) return allVariables
      const lower = searchText.toLowerCase()
      return allVariables.filter(v => v.name.toLowerCase().includes(lower))
    }, [allVariables, searchText])

    // 检测是否在输入变量引用
    const checkVariableInput = React.useCallback((inputValue: string, cursorPos: number) => {
      // 从光标位置向前查找 {
      let braceStart = -1
      for (let i = cursorPos - 1; i >= 0; i--) {
        if (inputValue[i] === '}') break
        if (inputValue[i] === '{') {
          braceStart = i
          break
        }
      }

      if (braceStart !== -1) {
        const textAfterBrace = inputValue.slice(braceStart + 1, cursorPos)
        // 检查是否包含非法字符（如空格后的内容）
        if (!textAfterBrace.includes('}')) {
          setSearchText(textAfterBrace)
          setShowSuggestions(true)
          setSelectedIndex(0)
          return
        }
      }

      setShowSuggestions(false)
      setSearchText('')
    }, [])

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const inputValue = e.target.value
      const pos = e.target.selectionStart || 0
      setCursorPosition(pos)
      setDisplayValue(inputValue)
      
      // 检查是否在输入变量
      checkVariableInput(inputValue, pos)

      // Preserve partial/invalid text in the document; never parse only its numeric prefix.
      const parsed = hasVariableRef(inputValue) ? null : parseNumber(inputValue)
      emitValue(parsed === null ? inputValue : parsed)
    }

    const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
      setTimeout(() => setShowSuggestions(false), 150)
      const parsed = parseNumber(displayValue)
      if (!validationError && parsed !== null && !hasVariableRef(displayValue)) {
        setDisplayValue(String(parsed))
        emitValue(parsed)
      }
      props.onBlur?.(e)
    }

    const insertVariable = (varName: string) => {
      const input = inputRef.current
      if (!input) return

      // 找到 { 的位置
      let braceStart = -1
      for (let i = cursorPosition - 1; i >= 0; i--) {
        if (displayValue[i] === '{') {
          braceStart = i
          break
        }
      }

      if (braceStart !== -1) {
        const before = displayValue.slice(0, braceStart + 1)
        const after = displayValue.slice(cursorPosition)
        const newValue = before + varName + '}' + after
        setDisplayValue(newValue)
        emitValue(newValue)
        
        // 设置光标位置到变量名后面
        setTimeout(() => {
          const newPos = braceStart + varName.length + 2
          input.setSelectionRange(newPos, newPos)
          input.focus()
        }, 0)
      }

      setShowSuggestions(false)
      setSearchText('')
    }

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (!showSuggestions || filteredVariables.length === 0) {
        props.onKeyDown?.(e)
        return
      }

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
          if (filteredVariables[selectedIndex]) {
            insertVariable(filteredVariables[selectedIndex].name)
          }
          break
        case 'Escape':
          setShowSuggestions(false)
          break
        default:
          props.onKeyDown?.(e)
      }
    }

    const handleClick = (e: React.MouseEvent<HTMLInputElement>) => {
      const cursorPos = e.currentTarget.selectionStart || 0
      setCursorPosition(cursorPos)
      checkVariableInput(displayValue, cursorPos)
      props.onClick?.(e)
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

    // 当选中索引变化时，自动滚动到选中项
    React.useEffect(() => {
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

    return (
      <div className="relative">
        <input
          {...props}
          type="text"
          inputMode={hasVariableRef(displayValue) ? 'text' : 'numeric'}
          className={cn(
            'flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
            className
          )}
          ref={inputRef}
          value={displayValue}
          onChange={handleChange}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          onClick={handleClick}
          aria-invalid={validationError ? true : props['aria-invalid']}
          aria-describedby={[props['aria-describedby'], validationError ? errorId : ''].filter(Boolean).join(' ') || undefined}
        />
        {validationError && <p id={errorId} role="alert" className="mt-1 text-xs text-[hsl(var(--danger-600))]">{validationError}</p>}
        
        {/* 变量提示下拉框 */}
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
                    index === selectedIndex ? 'bg-blue-100 text-blue-900' : 'hover:bg-muted'
                  )}
                  onClick={() => insertVariable(variable.name)}
                  onMouseEnter={() => setSelectedIndex(index)}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-blue-600">{variable.name}</span>
                    <span className={cn('text-xs', getTypeColor(variable.type))}>
                      ({variable.type})
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground truncate max-w-[120px]">
                    {formatValue(variable.value)}
                  </span>
                </div>
              ))}
            </div>
            <div className="border-t px-2 py-1 text-[10px] text-muted-foreground bg-muted/50">
              ↑↓ 选择 · Enter 确认 · Esc 关闭
            </div>
          </div>
        )}
        
        {/* 无匹配变量时的提示 */}
        {showSuggestions && filteredVariables.length === 0 && (
          <div className="absolute z-50 mt-1 w-full rounded-md border border-gray-200 bg-white shadow-lg p-3 text-sm animate-scale-in">
            {allVariables.length === 0 ? (
              <div className="text-muted-foreground">
                <p className="font-medium text-amber-600">暂无可用变量</p>
                <p className="text-xs mt-1">请先在"全局变量"面板中添加变量，或在模块中配置"存储变量名"</p>
              </div>
            ) : (
              <div className="text-muted-foreground">
                未找到匹配的变量 "<span className="text-blue-600">{searchText}</span>"
              </div>
            )}
          </div>
        )}
      </div>
    )
  }
)
NumberInput.displayName = 'NumberInput'

export { NumberInput }
