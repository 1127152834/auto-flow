// Source: WebRPA@5ccb900e, components/ui/url-input.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState, useRef, useEffect, useMemo } from 'react'
import { Link } from 'lucide-react'
import { VariableInput } from './variable-input'
import { useWorkflowStore } from '../../editor-store'
import { cn } from '../../lib/utils'

interface UrlInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

export function UrlInput({ value, onChange, placeholder, className }: UrlInputProps) {
  const nodes = useWorkflowStore((state) => state.nodes)
  const [showUrlList, setShowUrlList] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // 从工作流节点中提取所有URL（去重）
  const workflowUrls = useMemo(() => {
    return nodes
      .filter(n => n.data.moduleType === 'open_page' && n.data.url)
      .map(n => n.data.url as string)
      .filter((url, index, self) => self.indexOf(url) === index)
      .filter(url => url !== value) // 排除当前值
  }, [nodes, value])

  // 点击外部关闭
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowUrlList(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div ref={containerRef} className="relative">
      <div onFocus={() => setShowUrlList(true)}>
        <VariableInput
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          className={className}
        />
      </div>
      {/* URL列表弹窗 */}
      {showUrlList && workflowUrls.length > 0 && (
        <div className="absolute z-50 mt-1 w-full max-h-40 overflow-auto rounded-md border border-gray-200 bg-white shadow-lg">
          <div className="px-2 py-1.5 text-xs text-gray-500 border-b bg-gray-50">
            流程中的网址
          </div>
          {workflowUrls.map((url, i) => (
            <div
              key={i}
              className={cn(
                'px-2 py-1.5 text-sm cursor-pointer hover:bg-blue-50 flex items-center gap-2'
              )}
              onClick={() => {
                onChange(url)
                setShowUrlList(false)
              }}
            >
              <Link className="w-3 h-3 text-gray-400 flex-shrink-0" />
              <span className="truncate text-blue-600" title={url}>
                {url}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
