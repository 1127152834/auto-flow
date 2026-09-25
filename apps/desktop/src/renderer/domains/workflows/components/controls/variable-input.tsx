import { useProjectInputs, projectReferences, registerProjectReference } from '../../project-inputs'
// Source: WebRPA@5ccb900e, components/ui/variable-input.tsx; see SOURCE.md for license and adaptation boundaries.
import * as React from 'react'
import { cn } from '../../lib/utils'
import { useWorkflowStore, moduleTypeLabels } from '../../editor-store'
import { getModuleDefaultVar, VARIABLE_NAME_FIELDS } from '../../lib/moduleDefaultVars'
import type { Variable } from '../../types/index'

export interface VariableInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement | HTMLTextAreaElement>, 'onChange'> {
  value: string
  onChange: (value: string) => void
  /** 是否禁用变量提示（用于变量名输入框） */
  disableVariableHint?: boolean
  /** 是否使用多行文本框 */
  multiline?: boolean
  /** 多行文本框的行数 */
  rows?: number
}

/**
 * 支持变量引用的输入框组件
 * - 输入 { 时显示变量列表
 * - 支持键盘上下选择和回车确认
 * - 支持模糊搜索变量名
 * - 支持多行输入模式
 * - 自动识别模块配置中定义的变量
 * - 内置 ERROR 变量（隐含全局变量，不在变量面板显示）
 */

/** 系统内置隐含变量列表（在自动补全中显示，但不在变量面板中展示） */
const BUILTIN_HIDDEN_VARIABLES: Variable[] = [
  {
    name: 'ERROR',
    value: undefined,
    type: 'object',
    scope: 'global',
    description: '当模块报错或超时时，自动存入该模块的详细错误信息（node/nodeId/nodeType/error/isTimeout）',
    builtin: true,
  },
]
const VariableInput = React.forwardRef<HTMLInputElement | HTMLTextAreaElement, VariableInputProps>(
  ({ className, value, onChange, disableVariableHint = false, multiline = false, rows = 3, ...props }, ref) => {
    const projectAutomation = useProjectInputs(state => state.automation)
    const projectFields = useProjectInputs(state => state.fields)
    const globalVariables = useWorkflowStore((state) => state.variables)
    const nodes = useWorkflowStore((state) => state.nodes)
    
    // 收集所有变量（全局变量 + 模块定义的变量 + 内置隐含变量）
    const allVariables = React.useMemo(() => {
      const variableMap = new Map<string, Variable>()
      
      // 首先添加内置隐含变量（优先级最高，始终存在）
      BUILTIN_HIDDEN_VARIABLES.forEach(v => {
        variableMap.set(v.name, v)
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

          // 如果字段没有值，尝试用集中表里的默认变量名
          if (!varName || !varName.trim()) {
            varName = getModuleDefaultVar(moduleType, field)
          }

          if (typeof varName === 'string' && varName.trim() && !variableMap.has(varName)) {
            // 根据模块类型推断变量类型
            let varType: Variable['type'] = 'string'
            const moduleType = data.moduleType as string
            
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
            } else if (moduleType === 'webhook_trigger' || moduleType === 'email_trigger' || moduleType === 'api_trigger') {
              // 触发器返回的数据通常是对象
              varType = 'object'
            } else if (moduleType === 'element_change_trigger' && field === 'saveChangeInfo') {
              // 元素变化信息是对象
              varType = 'object'
            } else if (moduleType === 'math_base_convert') {
              varType = 'string'
            }
            
            variableMap.set(varName, {
              name: varName,
              value: undefined,
              type: varType,
              scope: 'local',
              description: `来自「${(data.name as string) || moduleTypeLabels[moduleType as keyof typeof moduleTypeLabels] || moduleType}」`,
            })
          }
        })
      })
      
      for (const reference of projectReferences(projectAutomation, projectFields)) variableMap.set(reference.name, { name: reference.name, value: undefined, type: (reference.type === 'date' ? 'string' : reference.type) as Variable['type'], scope: 'local', description: reference.label })
      return Array.from(variableMap.values())
    }, [globalVariables, nodes, projectAutomation, projectFields])
    
    const [showSuggestions, setShowSuggestions] = React.useState(false)
    const [selectedIndex, setSelectedIndex] = React.useState(0)
    const [searchText, setSearchText] = React.useState('')
    const [cursorPosition, setCursorPosition] = React.useState(0)
    const inputRef = React.useRef<HTMLInputElement | HTMLTextAreaElement>(null)
    const suggestionsRef = React.useRef<HTMLDivElement>(null)

    // 合并 ref
    React.useImperativeHandle(ref, () => inputRef.current!)

    // 过滤变量列表
    const filteredVariables = React.useMemo(() => {
      if (!searchText) return allVariables
      const lower = searchText.toLowerCase()
      return allVariables.filter(v => (v.name + ' ' + (v.description ?? '')).toLowerCase().includes(lower))
    }, [allVariables, searchText])

    // 检测是否在输入变量引用
    const checkVariableInput = React.useCallback((inputValue: string, cursorPos: number) => {
      if (disableVariableHint) return

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
    }, [disableVariableHint])

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const newValue = e.target.value
      const cursorPos = e.target.selectionStart || 0
      setCursorPosition(cursorPos)
      onChange(newValue)
      checkVariableInput(newValue, cursorPos)
    }

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
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
          // 多行模式下，只有在显示建议时才阻止默认行为
          if (showSuggestions && filteredVariables.length > 0) {
            e.preventDefault()
            insertVariable(filteredVariables[selectedIndex].name)
          }
          break
        case 'Tab':
          e.preventDefault()
          insertVariable(filteredVariables[selectedIndex].name)
          break
        case 'Escape':
          setShowSuggestions(false)
          break
      }
    }

    const insertVariable = (varName: string) => {
      registerProjectReference(varName)
      const input = inputRef.current
      if (!input) return

      // 找到 { 的位置
      let braceStart = -1
      for (let i = cursorPosition - 1; i >= 0; i--) {
        if (value[i] === '{') {
          braceStart = i
          break
        }
      }

      if (braceStart !== -1) {
        const before = value.slice(0, braceStart + 1)
        const after = value.slice(cursorPosition)
        const newValue = before + varName + '}' + after
        onChange(newValue)
        
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

    const handleBlur = () => {
      // 延迟关闭，允许点击选项
      setTimeout(() => setShowSuggestions(false), 150)
    }

    const handleClick = (e: React.MouseEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const cursorPos = (e.target as HTMLInputElement | HTMLTextAreaElement).selectionStart || 0
      setCursorPosition(cursorPos)
      checkVariableInput(value, cursorPos)
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
        {multiline ? (
          <textarea
            className={cn(
              'flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 resize-none',
              className
            )}
            ref={inputRef as React.RefObject<HTMLTextAreaElement>}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onBlur={handleBlur}
            onClick={handleClick}
            rows={rows}
            {...(props as React.TextareaHTMLAttributes<HTMLTextAreaElement>)}
          />
        ) : (
          <input
            type="text"
            className={cn(
              'flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
              className
            )}
            ref={inputRef as React.RefObject<HTMLInputElement>}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onBlur={handleBlur}
            onClick={handleClick}
            {...(props as React.InputHTMLAttributes<HTMLInputElement>)}
          />
        )}
        
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
                    <span className="font-mono text-blue-600">{variable.name.startsWith('PROJECT_') ? variable.description : variable.name}</span>
                    <span className={cn('text-xs', getTypeColor(variable.type))}>
                      ({variable.type})
                    </span>
                    {variable.builtin && (
                      <span className="text-[10px] px-1 py-0.5 rounded bg-amber-100 text-amber-700 border border-amber-200">
                        内置
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground truncate max-w-[120px]">
                    {variable.description ? variable.description.slice(0, 30) + (variable.description.length > 30 ? '…' : '') : formatValue(variable.value)}
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
VariableInput.displayName = 'VariableInput'

export { VariableInput }
