// Source: WebRPA@5ccb900e, components/ui/path-input.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState, useEffect, useRef } from 'react'
import { Button } from './button'
import { VariableInput } from './variable-input'
import { Folder, File, Loader2 } from 'lucide-react'
import { getStudioTransportRevision } from '../../api/transport'
import { systemApi } from '../../api'
import { cn } from '../../lib/utils'

interface PathInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
  /** both：同时给出「选文件夹」「选文件」两个按钮，用于既可填文件也可填文件夹的场景（如文件监控） */
  type?: 'folder' | 'file' | 'both'
  title?: string
  fileTypes?: Array<[string, string]>  // 文件类型过滤器，如 [["Excel文件", "*.xlsx"]]
}

export function PathInput({
  value,
  onChange,
  placeholder,
  className,
  type = 'folder',
  title,
  fileTypes,
}: PathInputProps) {
  const [isSelecting, setIsSelecting] = useState(false)
  const [error, setError] = useState('')
  const request = useRef(0)
  const pending = useRef(false)
  const mounted = useRef(false)
  useEffect(() => {
    mounted.current = true
    const invalidate = () => { request.current++; setError('') }
    window.addEventListener('studio:transport-changed', invalidate)
    return () => { mounted.current = false; request.current++; window.removeEventListener('studio:transport-changed', invalidate) }
  }, [])
  useEffect(() => { request.current++; setError('') }, [value, type])

  const handleSelect = async (mode: 'folder' | 'file' = type === 'both' ? 'folder' : type) => {
    if (pending.current) return
    pending.current = true
    const sequence = ++request.current
    const revision = getStudioTransportRevision()
    const current = () => mounted.current && sequence === request.current && revision === getStudioTransportRevision()
    setIsSelecting(true)
    setError('')
    try {
      const result = mode === 'folder'
        ? await systemApi.selectFolder(title || '选择文件夹')
        : await systemApi.selectFile(title || '选择文件', undefined, fileTypes)
      if (!current()) return
      if (!result?.success) throw new Error(result?.error || '选择路径失败')
      // Preserve the migrated wrapped and legacy flat success contracts.
      const inner = result.data && typeof result.data === 'object' ? result.data : result
      if (typeof inner.success !== 'boolean') throw new Error('路径选择响应格式错误')
      if (typeof inner.error === 'string' && inner.error) throw new Error(inner.error)
      if (inner.success === false && inner.path !== null) throw new Error('选择路径失败')
      const path: unknown = inner.path
      if (path === null || path === '') return
      if (typeof path !== 'string') throw new Error('服务返回了无效路径')
      onChange(path)
    } catch (reason) {
      if (current()) setError(reason instanceof Error ? reason.message : '选择路径失败')
    } finally {
      pending.current = false
      if (mounted.current) setIsSelecting(false)
    }
  }

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div className="flex gap-1">
      <div className="flex-1">
        <VariableInput
          value={value}
          onChange={onChange}
          placeholder={placeholder}
        />
      </div>
      {/* both 时给两个按钮：既能选文件夹也能选文件（如文件监控触发器） */}
      {type === 'both' ? (
        <>
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={() => handleSelect('folder')}
            disabled={isSelecting}
            title="选择文件夹"
            className="shrink-0"
          >
            {isSelecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Folder className="w-4 h-4" />}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={() => handleSelect('file')}
            disabled={isSelecting}
            title="选择文件"
            className="shrink-0"
          >
            {isSelecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <File className="w-4 h-4" />}
          </Button>
        </>
      ) : (
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => handleSelect()}
          disabled={isSelecting}
          title={type === 'folder' ? '选择文件夹' : '选择文件'}
          className="shrink-0"
        >
          {isSelecting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : type === 'folder' ? (
            <Folder className="w-4 h-4" />
          ) : (
            <File className="w-4 h-4" />
          )}
        </Button>
      )}
      </div>
      {error && <p role="alert" className="text-xs text-red-600">{error}</p>}
    </div>
  )
}
