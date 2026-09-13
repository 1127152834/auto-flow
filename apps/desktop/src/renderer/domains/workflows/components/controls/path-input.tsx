// Source: WebRPA@5ccb900e, components/ui/path-input.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState } from 'react'
import { Button } from './button'
import { VariableInput } from './variable-input'
import { Folder, File, Loader2 } from 'lucide-react'
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

  const handleSelect = async (mode: 'folder' | 'file' = type === 'both' ? 'folder' : (type as 'folder' | 'file')) => {
    setIsSelecting(true)
    try {
      // 兼容两种返回结构：apiRequest 包过的 {success, data: {success, path}}
      // 和直接的 {success, path}
      const extractPath = (resp: any): string | null => {
        if (!resp) return null
        const inner = resp.data && typeof resp.data === 'object' ? resp.data : resp
        if (inner?.success && typeof inner.path === 'string' && inner.path) {
          return inner.path
        }
        // 极端情况：path 在 resp 顶层
        if (typeof resp.path === 'string' && resp.path) return resp.path
        return null
      }

      if (mode === 'folder') {
        const result = await systemApi.selectFolder(title || '选择文件夹')
        const p = extractPath(result)
        console.log('[PathInput][folder] 后端返回:', result, '解析到 path:', p)
        if (p) {
          onChange(p)
        } else {
          console.warn('[PathInput] 文件夹选择未拿到 path:', result)
        }
      } else {
        const result = await systemApi.selectFile(title || '选择文件', undefined, fileTypes)
        const p = extractPath(result)
        console.log('[PathInput][file] 后端返回:', result, '解析到 path:', p)
        if (p) {
          onChange(p)
        } else {
          console.warn('[PathInput] 文件选择未拿到 path:', result)
        }
      }
    } catch (error) {
      console.error('选择路径失败:', error)
    } finally {
      setIsSelecting(false)
    }
  }

  return (
    <div className={cn('flex gap-1', className)}>
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
  )
}
