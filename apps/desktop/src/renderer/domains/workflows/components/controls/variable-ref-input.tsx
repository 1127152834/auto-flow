// Source: WebRPA@5ccb900e, components/ui/variable-ref-input.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { Input } from './input'
import { useWorkflowStore } from '../../editor-store'
import { getModuleAllDefaultVars, VARIABLE_NAME_FIELDS } from '../../lib/moduleDefaultVars'
import { cn } from '../../lib/utils'

interface VariableRefInputProps {
  id?: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

// 模块类型对应的默认变量值（统一改用中央 moduleDefaultVars，避免重复维护）

/**
 * 变量引用输入组件
 * 用于输入已存在的变量名，带有自动补全功能
 * 只允许字母、数字、下划线和中文
 */
export function VariableRefInput({
  id,
  value,
  onChange,
  placeholder,
  className,
}: VariableRefInputProps) {
  const globalVars = useWorkflowStore((state) => state.variables)
  const nodes = useWorkflowStore((state) => state.nodes)
  const [showPopup, setShowPopup] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const popupRef = useRef<HTMLDivElement>(null)

  // 从节点中提取所有定义的变量
  const allVars = useMemo(() => {
    const vars: Array<{ name: string; type: string; source: string }> = []
    const seen = new Set<string>()

    // 首先添加内置隐含变量
    if (!seen.has('ERROR')) {
      seen.add('ERROR')
      vars.push({ name: 'ERROR', type: 'object', source: '内置' })
    }

    // 添加全局变量
    for (const v of globalVars) {
      if (!seen.has(v.name)) {
        seen.add(v.name)
        vars.push({ name: v.name, type: v.type, source: '全局' })
      }
    }

    // 从节点配置中提取变量
    for (const node of nodes) {
      const data = node.data as Record<string, unknown>
      const moduleType = data.moduleType as string
      const nodeLabel = (data.name as string) || (data.label as string) || moduleType
      
      const defaultVars = getModuleAllDefaultVars(moduleType)
      
      for (const field of VARIABLE_NAME_FIELDS) {
        let varName = data[field] as string | undefined
        if (!varName && defaultVars[field]) {
          varName = defaultVars[field]
        }
        
        if (typeof varName === 'string' && varName.trim() && !seen.has(varName)) {
          seen.add(varName)
          
          let varType = 'string'
          if (moduleType === 'list_operation' || moduleType === 'dict_keys' || moduleType === 'read_excel' || moduleType === 'list_sort' || moduleType === 'list_unique' || moduleType === 'list_slice') {
            varType = 'array'
          } else if (moduleType === 'dict_operation' || moduleType === 'json_parse') {
            varType = 'object'
          } else if (moduleType === 'random_number' || moduleType === 'list_length' || moduleType === 'list_get' || moduleType === 'list_sum' || moduleType === 'list_average' || moduleType === 'list_max' || moduleType === 'list_min' || moduleType === 'math_round' || moduleType === 'math_floor' || moduleType === 'math_modulo' || moduleType === 'math_abs' || moduleType === 'math_sqrt' || moduleType === 'math_power') {
            varType = 'number'
          } else if ((moduleType === 'foreach' || moduleType === 'loop' || moduleType === 'foreach_dict') && field === 'indexVariable') {
            varType = 'number'
          } else if (moduleType === 'foreach' && field === 'itemVariable') {
            varType = 'any'
          } else if (moduleType === 'foreach_dict' && (field === 'keyVariable' || field === 'valueVariable')) {
            varType = 'any'
          } else if (moduleType === 'webhook_trigger' || moduleType === 'email_trigger' || moduleType === 'api_trigger') {
            varType = 'object'
          } else if (moduleType === 'element_change_trigger' && field === 'saveChangeInfo') {
            varType = 'object'
          } else if (moduleType === 'math_base_convert') {
            varType = 'string'
          }
          
          vars.push({ name: varName, type: varType, source: nodeLabel })
        }
      }
    }

    return vars
  }, [globalVars, nodes])

  // 过滤变量列表
  const filteredVars = useMemo(
    () =>
      allVars.filter((v) =>
        v.name.toLowerCase().includes(value.toLowerCase())
      ),
    [allVars, value]
  )

  // 处理输入变化
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    // 过滤非法字符，只保留字母、数字、下划线和中文
    const filtered = newValue.replace(/[^a-zA-Z0-9_\u4e00-\u9fa5]/g, '')
    onChange(filtered)
    
    // 显示自动补全
    if (filtered) {
      setShowPopup(true)
      setSelectedIndex(0)
    } else {
      setShowPopup(false)
    }
  }

  // 处理聚焦
  const handleFocus = () => {
    if (value || allVars.length > 0) {
      setShowPopup(true)
      setSelectedIndex(0)
    }
  }

  // 选择变量
  const selectVariable = useCallback(
    (varName: string) => {
      onChange(varName)
      setShowPopup(false)
      inputRef.current?.focus()
    },
    [onChange]
  )

  // 当选中索引变化时，自动滚动到选中项
  useEffect(() => {
    if (!showPopup || selectedIndex < 0 || selectedIndex >= filteredVars.length) {
      return
    }

    const container = popupRef.current
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
  }, [selectedIndex, showPopup, filteredVars])

  // 键盘导航
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showPopup || filteredVars.length === 0) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((i) => (i + 1) % filteredVars.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((i) => (i - 1 + filteredVars.length) % filteredVars.length)
    } else if (e.key === 'Enter' || e.key === 'Tab') {
      if (filteredVars.length > 0) {
        e.preventDefault()
        selectVariable(filteredVars[selectedIndex].name)
      }
    } else if (e.key === 'Escape') {
      setShowPopup(false)
    }
  }

  // 点击外部关闭
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        popupRef.current &&
        !popupRef.current.contains(e.target as Node) &&
        !inputRef.current?.contains(e.target as Node)
      ) {
        setShowPopup(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // 检查当前值是否是有效变量
  const isValidVar = allVars.some((v) => v.name === value)

  return (
    <div className="relative">
      <Input
        ref={inputRef}
        id={id}
        value={value}
        onChange={handleChange}
        onFocus={handleFocus}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className={cn(
          isValidVar && 'text-blue-600',
          className
        )}
      />
      {showPopup && (
        <div
          ref={popupRef}
          className="absolute z-50 mt-1 w-full max-h-48 overflow-auto rounded-md border border-gray-200 bg-white shadow-lg"
        >
          {filteredVars.length > 0 ? (
            filteredVars.map((v, i) => (
              <div
                key={v.name}
                data-index={i}
                className={cn(
                  'px-3 py-1.5 text-sm cursor-pointer',
                  i === selectedIndex ? 'bg-blue-50' : 'hover:bg-gray-50'
                )}
                onClick={() => selectVariable(v.name)}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-blue-600">{v.name}</span>
                  <span className="text-xs text-gray-500">{v.type}</span>
                </div>
                <div className="text-[10px] text-gray-400 truncate">
                  来源: {v.source}
                </div>
              </div>
            ))
          ) : value ? (
            <div className="px-3 py-2 text-xs text-gray-500 text-center">
              未找到变量 "{value}"
            </div>
          ) : (
            <div className="px-3 py-2 text-xs text-gray-500 text-center">
              暂无可用变量
            </div>
          )}
        </div>
      )}
    </div>
  )
}
